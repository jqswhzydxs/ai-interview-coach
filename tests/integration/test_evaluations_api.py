from collections.abc import Iterator
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.models.evaluation import AnswerEvaluation
from app.db.models.memory import MemoryItem
from app.db.models.question import InterviewQuestion
from app.main import create_app
from tests.integration.test_questions_api import create_prep_package


@pytest.fixture()
def client_and_session(tmp_path, monkeypatch) -> Iterator[tuple[TestClient, sessionmaker]]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'evaluations.db'}"
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


def first_question_id(client: TestClient, prep_package_id: str) -> str:
    response = client.get(f"/api/v1/prep-packages/{prep_package_id}/questions")
    assert response.status_code == 200
    return response.json()["data"]["items"][0]["question_db_id"]


def test_create_question_bank_answer_evaluation(client_and_session) -> None:
    client, SessionLocal = client_and_session
    prep_package_id = create_prep_package(client)
    question_db_id = first_question_id(client, prep_package_id)

    response = client.post(
        "/api/v1/evaluations",
        json={
            "question_db_id": question_db_id,
            "user_answer": "I built APIs with FastAPI and PostgreSQL.",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["answer_evaluation_id"]
    assert 0 <= data["total_score"] <= 100

    with SessionLocal() as session:
        evaluation = session.get(AnswerEvaluation, UUID(data["answer_evaluation_id"]))
        question = session.get(InterviewQuestion, UUID(question_db_id))

    assert evaluation.question_db_id == question.id
    assert evaluation.prep_package_id == UUID(prep_package_id)


def test_create_evaluation_persists_high_confidence_memory_update(
    client_and_session,
) -> None:
    client, SessionLocal = client_and_session
    prep_package_id = create_prep_package(client)
    question_db_id = first_question_id(client, prep_package_id)

    response = client.post(
        "/api/v1/evaluations",
        json={
            "question_db_id": question_db_id,
            "user_answer": "I built APIs with FastAPI and PostgreSQL.",
        },
    )

    assert response.status_code == 200
    answer_evaluation_id = UUID(response.json()["data"]["answer_evaluation_id"])

    with SessionLocal() as session:
        memory_items = session.scalars(
            select(MemoryItem).where(MemoryItem.source_id == answer_evaluation_id)
        ).all()

    assert len(memory_items) == 1
    assert memory_items[0].source_type == "answer_evaluation"


def test_create_custom_question_answer_evaluation(client_and_session) -> None:
    client, _ = client_and_session

    response = client.post(
        "/api/v1/evaluations",
        json={
            "custom_question_text": "Explain a backend project you built.",
            "user_answer": "I worked on FastAPI APIs.",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["answer_evaluation_id"]


def test_get_evaluation_detail_and_history(client_and_session) -> None:
    client, _ = client_and_session
    create_response = client.post(
        "/api/v1/evaluations",
        json={
            "custom_question_text": "Explain a backend project you built.",
            "user_answer": "I worked on FastAPI APIs.",
        },
    )
    answer_evaluation_id = create_response.json()["data"]["answer_evaluation_id"]

    detail_response = client.get(f"/api/v1/evaluations/{answer_evaluation_id}")
    history_response = client.get("/api/v1/evaluations", params={"limit": 10, "offset": 0})

    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["answer_evaluation_id"] == answer_evaluation_id
    assert detail["improved_answer"]
    assert detail["follow_up_questions"]

    assert history_response.status_code == 200
    history = history_response.json()["data"]
    assert history["total"] >= 1
    assert len(history["items"]) >= 1
