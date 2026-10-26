from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture()
def client_and_session(tmp_path, monkeypatch) -> Iterator[tuple[TestClient, sessionmaker]]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'agent_runs.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")

    app = create_app()
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with TestClient(app) as client:
        yield client, SessionLocal

    get_settings.cache_clear()


def create_agent_run(client: TestClient) -> str:
    response = client.post(
        "/api/v1/evaluations",
        json={
            "custom_question_text": "Explain a backend project.",
            "user_answer": "I built FastAPI APIs with PostgreSQL.",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["agent_run_id"]


def test_get_agent_run_detail(client_and_session) -> None:
    client, _ = client_and_session
    agent_run_id = create_agent_run(client)

    response = client.get(f"/api/v1/agent-runs/{agent_run_id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["agent_run_id"] == agent_run_id
    assert data["run_type"] == "answer_evaluation"
    assert data["status"] == "succeeded"
    assert data["prompt_version"] == "answer_evaluator_v0.1"
    assert [step["step_order"] for step in data["steps"]] == [1]
    assert "I built FastAPI APIs" not in str(data)
    assert data["execution_mode"] == "mock"
    assert data["provider"] == "mock"
    assert data["real_call_count"] == 0
    assert data["retry_count"] == 0
    assert data["fallback_reason"] is None


def test_missing_agent_run_returns_not_found(client_and_session) -> None:
    client, _ = client_and_session

    response = client.get("/api/v1/agent-runs/00000000-0000-0000-0000-000000000999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
