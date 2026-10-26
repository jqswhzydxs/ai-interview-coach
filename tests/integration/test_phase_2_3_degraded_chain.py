from collections.abc import Iterator
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.models.agent_run import AgentRun, AgentRunStep
from app.db.models.evaluation import AnswerEvaluation
from app.db.models.memory import MemoryItem
from app.db.models.prep_package import InterviewPrepPackage
from app.main import create_app
from tests.integration.test_questions_api import create_prep_package


@pytest.fixture()
def client_and_session(tmp_path, monkeypatch) -> Iterator[tuple[TestClient, sessionmaker]]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'phase23.db'}"
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


def test_question_fallback_propagates_to_degraded_api_and_blocks_memory(
    client_and_session,
) -> None:
    client, SessionLocal = client_and_session
    prep_package_id = create_prep_package(client)
    questions = client.get(
        f"/api/v1/prep-packages/{prep_package_id}/questions"
    ).json()["data"]["items"]
    question_db_id = questions[0]["question_db_id"]

    with SessionLocal() as session:
        package = session.get(InterviewPrepPackage, UUID(prep_package_id))
        question_run = session.get(AgentRun, package.agent_run_id)
        question_run.execution_mode = "fallback"
        question_run.fallback_reason_json = {
            "code": "synthetic_question_fallback",
            "failure_type": "provider",
            "stage": "provider_call",
            "attempt": 2,
        }
        session.commit()

    response = client.post(
        "/api/v1/evaluations",
        json={
            "question_db_id": question_db_id,
            "user_answer": "I used a bounded example and explained the tradeoff.",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["evaluation_mode"] == "degraded"
    assert data["score_available"] is False
    assert data["source_quality"] == "degraded"
    assert data["total_score"] is None
    assert "upstream_fallback:question" in data["degradation_reasons"]

    detail = client.get(
        f"/api/v1/evaluations/{data['answer_evaluation_id']}"
    ).json()["data"]
    assert detail["evaluation"]["dimension_scores"] == []
    assert detail["memory_update"]["write_decision"] == "skip"

    run_detail = client.get(f"/api/v1/agent-runs/{data['agent_run_id']}").json()[
        "data"
    ]
    assert run_detail["execution_mode"] == "fallback"
    assert run_detail["real_call_count"] == 0
    assert run_detail["retry_count"] == 0
    assert run_detail["fallback_reason"]["code"] == "degraded_upstream_source"
    assert run_detail["failure_types"] == {"policy": 1}
    assert any(step["action_type"] == "fallback" for step in run_detail["steps"])

    with SessionLocal() as session:
        evaluation = session.get(AnswerEvaluation, UUID(data["answer_evaluation_id"]))
        memory_items = session.scalars(
            select(MemoryItem).where(MemoryItem.source_id == evaluation.id)
        ).all()
        steps = session.scalars(
            select(AgentRunStep).where(
                AgentRunStep.agent_run_id == evaluation.agent_run_id
            )
        ).all()

    assert evaluation.source_context_json["question"]["execution_mode"] == "fallback"
    assert memory_items == []
    assert [step.action_type for step in steps] == ["fallback"]
