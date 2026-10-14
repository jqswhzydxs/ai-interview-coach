import json
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'e2e.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()


def test_question_generation_and_evaluation_flow(client: TestClient) -> None:
    case = json.loads(
        Path("tests/fixtures/sample_cases/backend_python_case.json").read_text(
            encoding="utf-8"
        )
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
        json={"source_document_id": resume_doc_id, "title": "Python Backend Resume"},
    ).json()["data"]["resume_id"]
    job_description_id = client.post(
        "/api/v1/jobs",
        json={"source_document_id": jd_doc_id, "title": "Python Backend Engineer"},
    ).json()["data"]["job_description_id"]

    resume_parse = client.post(f"/api/v1/resumes/{resume_id}/parse")
    jd_parse = client.post(f"/api/v1/jobs/{job_description_id}/parse")
    assert resume_parse.status_code == 200
    assert jd_parse.status_code == 200

    prep_response = client.post(
        "/api/v1/prep-packages",
        json={
            "resume_id": resume_id,
            "job_description_id": job_description_id,
            "preparation_goal": case["preparation_goal"],
        },
    )
    assert prep_response.status_code == 200
    prep_package_id = prep_response.json()["data"]["prep_package_id"]

    package_detail = client.get(f"/api/v1/prep-packages/{prep_package_id}").json()["data"]
    assert package_detail["recommended_count"] == 3

    questions_response = client.get(f"/api/v1/prep-packages/{prep_package_id}/questions")
    assert questions_response.status_code == 200
    questions = questions_response.json()["data"]["items"]
    assert len(questions) >= 25

    module_counts = Counter(question["module"] for question in questions)
    assert module_counts["self_intro"] >= 8
    assert module_counts["professional"] >= 8
    assert module_counts["behavior_project"] >= 8

    evaluation_response = client.post(
        "/api/v1/evaluations",
        json={
            "question_db_id": questions[0]["question_db_id"],
            "user_answer": case["user_answer"],
        },
    )
    assert evaluation_response.status_code == 200
    evaluation_data = evaluation_response.json()["data"]
    assert 0 <= evaluation_data["total_score"] <= 100

    evaluation_detail = client.get(
        f"/api/v1/evaluations/{evaluation_data['answer_evaluation_id']}"
    ).json()["data"]
    assert evaluation_detail["improved_answer"]
    assert len(evaluation_detail["follow_up_questions"]) >= 1
    assert all(
        item["score"] <= item["max_score"]
        for item in evaluation_detail["evaluation"]["dimension_scores"]
    )

    agent_run_response = client.get(f"/api/v1/agent-runs/{evaluation_data['agent_run_id']}")
    assert agent_run_response.status_code == 200
    agent_run = agent_run_response.json()["data"]
    assert agent_run["status"] == "succeeded"
    assert len(agent_run["steps"]) >= 1
