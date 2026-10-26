import json
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.models.agent_run import AgentRun
from app.db.models.memory import MemoryItem
from app.db.models.prep_package import InterviewPrepPackage
from app.main import create_app


@pytest.fixture()
def client_and_session(tmp_path, monkeypatch) -> Iterator[tuple[TestClient, sessionmaker]]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'phase23-e2e.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")

    app = create_app()
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with TestClient(app) as client:
        yield client, SessionLocal
    get_settings.cache_clear()


def _create_flow(client: TestClient, case_name: str) -> tuple[dict, str, list[dict]]:
    case = json.loads(
        (Path("tests/fixtures/sample_cases") / case_name).read_text(encoding="utf-8")
    )
    resume_doc_id = client.post(
        "/api/v1/documents/text",
        json={"document_type": "resume", "raw_text": case["resume_text"]},
    ).json()["data"]["source_document_id"]
    jd_doc_id = client.post(
        "/api/v1/documents/text",
        json={"document_type": "jd", "raw_text": case["jd_text"]},
    ).json()["data"]["source_document_id"]
    resume_id = client.post(
        "/api/v1/resumes",
        json={"source_document_id": resume_doc_id, "title": case_name},
    ).json()["data"]["resume_id"]
    job_id = client.post(
        "/api/v1/jobs",
        json={"source_document_id": jd_doc_id, "title": "Backend Engineer"},
    ).json()["data"]["job_description_id"]
    assert client.post(f"/api/v1/resumes/{resume_id}/parse").status_code == 200
    assert client.post(f"/api/v1/jobs/{job_id}/parse").status_code == 200
    package_response = client.post(
        "/api/v1/prep-packages",
        json={
            "resume_id": resume_id,
            "job_description_id": job_id,
            "preparation_goal": case["preparation_goal"],
        },
    )
    assert package_response.status_code == 200
    package_id = package_response.json()["data"]["prep_package_id"]
    questions = client.get(
        f"/api/v1/prep-packages/{package_id}/questions"
    ).json()["data"]["items"]
    return case, package_id, questions


@pytest.mark.parametrize(
    ("case_name", "expected", "forbidden"),
    [
        ("backend_go_case.json", "Go", ["FastAPI", "Spring Boot"]),
        ("backend_java_case.json", "Java", ["FastAPI", "Gin"]),
        ("backend_python_case.json", "FastAPI", ["Spring Boot", "Gin"]),
    ],
)
def test_three_sample_cases_are_stack_specific_and_fully_offline(
    client_and_session,
    case_name: str,
    expected: str,
    forbidden: list[str],
) -> None:
    client, SessionLocal = client_and_session
    case, _, questions = _create_flow(client, case_name)
    texts = [question["question_text"] for question in questions]
    professional_text = " ".join(
        question["question_text"]
        for question in questions
        if question["module"] == "professional"
    )

    assert len(questions) == 25
    assert len({text.strip().casefold() for text in texts}) == 25
    assert expected in professional_text
    assert all(term not in professional_text for term in forbidden)

    professional = next(
        question for question in questions if question["module"] == "professional"
    )
    response = client.post(
        "/api/v1/evaluations",
        json={
            "question_db_id": professional["question_db_id"],
            "user_answer": case["user_answer"],
        },
    )
    assert response.status_code == 200
    evaluation = response.json()["data"]
    assert evaluation["evaluation_mode"] == "standard"
    assert evaluation["score_available"] is True
    assert evaluation["source_quality"] == "synthetic"
    assert evaluation["total_score"] == 76.0

    with SessionLocal() as session:
        runs = session.scalars(select(AgentRun)).all()
        memory_count = session.scalar(select(func.count(MemoryItem.id)))
    assert runs
    assert all(run.provider == "mock" for run in runs)
    assert all(run.real_call_count == 0 for run in runs)
    assert memory_count == 1


def test_fallback_question_end_to_end_has_no_score_and_no_long_term_memory(
    client_and_session,
) -> None:
    client, SessionLocal = client_and_session
    case, package_id, questions = _create_flow(client, "backend_go_case.json")

    with SessionLocal() as session:
        package = session.get(InterviewPrepPackage, UUID(package_id))
        question_run = session.get(AgentRun, package.agent_run_id)
        question_run.execution_mode = "fallback"
        question_run.fallback_reason_json = {
            "code": "synthetic_e2e_fallback",
            "failure_type": "provider",
            "stage": "provider_call",
            "attempt": 2,
        }
        session.commit()

    professional = next(
        question for question in questions if question["module"] == "professional"
    )
    response = client.post(
        "/api/v1/evaluations",
        json={
            "question_db_id": professional["question_db_id"],
            "user_answer": case["user_answer"],
        },
    )
    assert response.status_code == 200
    evaluation = response.json()["data"]
    assert evaluation["evaluation_mode"] == "degraded"
    assert evaluation["score_available"] is False
    assert evaluation["total_score"] is None

    detail = client.get(
        f"/api/v1/evaluations/{evaluation['answer_evaluation_id']}"
    ).json()["data"]
    assert detail["evaluation"]["dimension_scores"] == []
    assert detail["memory_update"]["write_decision"] == "skip"

    run = client.get(f"/api/v1/agent-runs/{evaluation['agent_run_id']}").json()[
        "data"
    ]
    assert run["execution_mode"] == "fallback"
    assert run["fallback_reason"]["code"] == "degraded_upstream_source"

    with SessionLocal() as session:
        assert session.scalar(select(func.count(MemoryItem.id))) == 0
