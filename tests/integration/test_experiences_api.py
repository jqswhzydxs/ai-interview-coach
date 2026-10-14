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
from app.db.models.interview_experience import ExperienceProfile, InterviewExperience
from app.main import create_app


@pytest.fixture()
def client_and_session(tmp_path, monkeypatch) -> Iterator[tuple[TestClient, sessionmaker]]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'experiences.db'}"
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


def create_experience_document(client: TestClient) -> str:
    response = client.post(
        "/api/v1/documents/text",
        json={
            "document_type": "interview_experience",
            "raw_text": "Interviewer asked FastAPI project details and database transaction tradeoffs.",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["source_document_id"]


def test_create_interview_experience_record(client_and_session) -> None:
    client, SessionLocal = client_and_session
    source_document_id = create_experience_document(client)

    response = client.post(
        "/api/v1/experiences",
        json={
            "source_document_id": source_document_id,
            "title": "Backend interview notes",
            "experience_type": "manual_note",
            "company_name": "Example Inc",
            "role_name": "Backend Engineer",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "Backend interview notes"
    assert data["source_document_id"] == source_document_id

    with SessionLocal() as session:
        experience = session.get(InterviewExperience, UUID(data["interview_experience_id"]))

    assert experience is not None
    assert "FastAPI" in experience.raw_text


def test_parse_interview_experience_creates_profile_and_agent_run(client_and_session) -> None:
    client, SessionLocal = client_and_session
    source_document_id = create_experience_document(client)
    create_response = client.post(
        "/api/v1/experiences",
        json={
            "source_document_id": source_document_id,
            "title": "Backend interview notes",
            "experience_type": "manual_note",
        },
    )
    interview_experience_id = create_response.json()["data"]["interview_experience_id"]

    response = client.post(f"/api/v1/experiences/{interview_experience_id}/parse")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["interview_experience_id"] == interview_experience_id
    assert data["experience_profile_id"]
    assert data["agent_run_id"]

    with SessionLocal() as session:
        profile = session.get(ExperienceProfile, UUID(data["experience_profile_id"]))
        run = session.get(AgentRun, UUID(data["agent_run_id"]))
        steps = session.scalars(
            select(AgentRunStep).where(AgentRunStep.agent_run_id == run.id)
        ).all()

    assert profile.interview_experience_id == UUID(interview_experience_id)
    assert profile.schema_version == "v0.1"
    assert "FastAPI" in profile.frequent_topics
    assert run.status == "succeeded"
    assert len(steps) == 1


def test_parse_missing_experience_returns_not_found(client_and_session) -> None:
    client, _ = client_and_session

    response = client.post(
        "/api/v1/experiences/00000000-0000-0000-0000-000000000999/parse"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
