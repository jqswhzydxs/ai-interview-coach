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
from app.db.models.resume import Resume, ResumeProfile
from app.main import create_app


@pytest.fixture()
def client_and_session(tmp_path, monkeypatch) -> Iterator[tuple[TestClient, sessionmaker]]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'resumes.db'}"
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


def create_resume_document(client: TestClient) -> str:
    response = client.post(
        "/api/v1/documents/text",
        json={
            "document_type": "resume",
            "raw_text": "Python backend developer. Built FastAPI and PostgreSQL projects.",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["source_document_id"]


def test_create_resume_record(client_and_session) -> None:
    client, SessionLocal = client_and_session
    source_document_id = create_resume_document(client)

    response = client.post(
        "/api/v1/resumes",
        json={
            "source_document_id": source_document_id,
            "title": "Backend Resume",
            "target_direction": "backend",
            "version_label": "v1",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "Backend Resume"
    assert data["source_document_id"] == source_document_id

    with SessionLocal() as session:
        resume = session.get(Resume, UUID(data["resume_id"]))

    assert resume is not None
    assert resume.is_active is True


def test_parse_resume_creates_profile_and_agent_run(client_and_session) -> None:
    client, SessionLocal = client_and_session
    source_document_id = create_resume_document(client)
    create_response = client.post(
        "/api/v1/resumes",
        json={"source_document_id": source_document_id, "title": "Backend Resume"},
    )
    resume_id = create_response.json()["data"]["resume_id"]

    response = client.post(f"/api/v1/resumes/{resume_id}/parse")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["resume_id"] == resume_id
    assert data["resume_profile_id"]
    assert data["agent_run_id"]

    with SessionLocal() as session:
        profile = session.get(ResumeProfile, UUID(data["resume_profile_id"]))
        run = session.get(AgentRun, UUID(data["agent_run_id"]))
        steps = session.scalars(
            select(AgentRunStep).where(AgentRunStep.agent_run_id == run.id)
        ).all()

    assert profile.resume_id == UUID(resume_id)
    assert profile.schema_version == "v0.1"
    assert "Python" in profile.skills
    assert run.status == "succeeded"
    assert len(steps) == 1


def test_parse_missing_resume_returns_not_found(client_and_session) -> None:
    client, _ = client_and_session

    response = client.post("/api/v1/resumes/00000000-0000-0000-0000-000000000999/parse")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
