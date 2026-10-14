from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.main import create_app
from tests.integration.test_prep_packages_api import prepare_resume_and_job


@pytest.fixture()
def client_and_session(tmp_path, monkeypatch) -> Iterator[tuple[TestClient, sessionmaker]]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'questions.db'}"
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


def create_prep_package(client: TestClient) -> str:
    resume_id, job_description_id = prepare_resume_and_job(client)
    response = client.post(
        "/api/v1/prep-packages",
        json={
            "resume_id": resume_id,
            "job_description_id": job_description_id,
            "preparation_goal": "Practice backend project deep dive",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["prep_package_id"]


def test_get_prep_package_detail(client_and_session) -> None:
    client, _ = client_and_session
    prep_package_id = create_prep_package(client)

    response = client.get(f"/api/v1/prep-packages/{prep_package_id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["prep_package_id"] == prep_package_id
    assert data["status"] == "ready"
    assert data["question_count"] >= 25


def test_get_prep_package_questions(client_and_session) -> None:
    client, _ = client_and_session
    prep_package_id = create_prep_package(client)

    response = client.get(f"/api/v1/prep-packages/{prep_package_id}/questions")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] >= 25
    assert len(data["items"]) >= 25


def test_filter_questions_by_module_and_difficulty(client_and_session) -> None:
    client, _ = client_and_session
    prep_package_id = create_prep_package(client)

    module_response = client.get(
        f"/api/v1/prep-packages/{prep_package_id}/questions",
        params={"module": "professional"},
    )
    difficulty_response = client.get(
        f"/api/v1/prep-packages/{prep_package_id}/questions",
        params={"difficulty": "basic"},
    )

    assert module_response.status_code == 200
    assert all(
        item["module"] == "professional" for item in module_response.json()["data"]["items"]
    )
    assert difficulty_response.status_code == 200
    assert all(
        item["difficulty"] == "basic" for item in difficulty_response.json()["data"]["items"]
    )
