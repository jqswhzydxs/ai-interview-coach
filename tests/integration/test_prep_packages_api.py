from collections.abc import Iterator
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.models.agent_run import AgentRun
from app.db.models.prep_package import InterviewPrepPackage, MatchReport, PrepPackageExperience
from app.db.models.question import InterviewQuestion, RecommendedQuestion
from app.main import create_app


@pytest.fixture()
def client_and_session(tmp_path, monkeypatch) -> Iterator[tuple[TestClient, sessionmaker]]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'prep_packages.db'}"
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


def prepare_resume_and_job(client: TestClient) -> tuple[str, str]:
    resume_doc = client.post(
        "/api/v1/documents/text",
        json={
            "document_type": "resume",
            "raw_text": "Python backend developer with FastAPI and PostgreSQL project.",
        },
    ).json()["data"]["source_document_id"]
    jd_doc = client.post(
        "/api/v1/documents/text",
        json={
            "document_type": "jd",
            "raw_text": "Backend Engineer requires Python, FastAPI, PostgreSQL and API design.",
        },
    ).json()["data"]["source_document_id"]

    resume_id = client.post(
        "/api/v1/resumes",
        json={"source_document_id": resume_doc, "title": "Backend Resume"},
    ).json()["data"]["resume_id"]
    job_description_id = client.post(
        "/api/v1/jobs",
        json={"source_document_id": jd_doc, "title": "Backend Engineer"},
    ).json()["data"]["job_description_id"]

    assert client.post(f"/api/v1/resumes/{resume_id}/parse").status_code == 200
    assert client.post(f"/api/v1/jobs/{job_description_id}/parse").status_code == 200
    return resume_id, job_description_id


def prepare_interview_experience(client: TestClient) -> str:
    experience_doc = client.post(
        "/api/v1/documents/text",
        json={
            "document_type": "interview_experience",
            "raw_text": "Backend interviews often ask FastAPI project tradeoffs and database indexes.",
        },
    ).json()["data"]["source_document_id"]
    experience_id = client.post(
        "/api/v1/experiences",
        json={
            "source_document_id": experience_doc,
            "title": "Backend interview notes",
            "experience_type": "manual",
            "company_name": "ExampleCo",
            "role_name": "Backend Engineer",
        },
    ).json()["data"]["interview_experience_id"]

    assert client.post(f"/api/v1/experiences/{experience_id}/parse").status_code == 200
    return experience_id


def test_create_prep_package_generates_questions_and_recommendations(
    client_and_session,
) -> None:
    client, SessionLocal = client_and_session
    resume_id, job_description_id = prepare_resume_and_job(client)

    response = client.post(
        "/api/v1/prep-packages",
        json={
            "resume_id": resume_id,
            "job_description_id": job_description_id,
            "preparation_goal": "Focus on backend project deep dive",
            "title": "Backend Interview Prep",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "ready"
    assert data["prep_package_id"]
    assert data["agent_run_id"]

    with SessionLocal() as session:
        package = session.get(InterviewPrepPackage, UUID(data["prep_package_id"]))
        run = session.get(AgentRun, UUID(data["agent_run_id"]))
        match_report = session.scalars(
            select(MatchReport).where(MatchReport.prep_package_id == package.id)
        ).one()
        questions = session.scalars(
            select(InterviewQuestion).where(InterviewQuestion.prep_package_id == package.id)
        ).all()
        recommended = session.scalars(
            select(RecommendedQuestion).where(RecommendedQuestion.prep_package_id == package.id)
        ).all()

    assert package.status == "ready"
    assert package.overview_json["preparation_goal"] == "Focus on backend project deep dive"
    assert run.input_summary_json["preparation_goal"] == "Focus on backend project deep dive"
    assert match_report.overall_score is not None
    assert len(questions) >= 25
    assert len(recommended) == 3


def test_create_prep_package_persists_optional_interview_experiences(
    client_and_session,
) -> None:
    client, SessionLocal = client_and_session
    resume_id, job_description_id = prepare_resume_and_job(client)
    experience_id = prepare_interview_experience(client)

    response = client.post(
        "/api/v1/prep-packages",
        json={
            "resume_id": resume_id,
            "job_description_id": job_description_id,
            "interview_experience_ids": [experience_id],
            "preparation_goal": "Use interview notes to prioritize project deep dive",
        },
    )

    assert response.status_code == 200
    prep_package_id = response.json()["data"]["prep_package_id"]

    with SessionLocal() as session:
        links = session.scalars(
            select(PrepPackageExperience).where(
                PrepPackageExperience.prep_package_id == UUID(prep_package_id)
            )
        ).all()

    assert len(links) == 1
    assert links[0].interview_experience_id == UUID(experience_id)
    assert links[0].experience_profile_id is not None


def test_create_prep_package_without_experiences_still_succeeds(client_and_session) -> None:
    client, _ = client_and_session
    resume_id, job_description_id = prepare_resume_and_job(client)

    response = client.post(
        "/api/v1/prep-packages",
        json={
            "resume_id": resume_id,
            "job_description_id": job_description_id,
            "preparation_goal": "Practice core backend questions",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ready"
