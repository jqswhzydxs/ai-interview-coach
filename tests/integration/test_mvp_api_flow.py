import json
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
    database_url = f"sqlite+pysqlite:///{tmp_path / 'mvp_flow.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()


def test_mvp_api_main_flow(client: TestClient) -> None:
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

    assert client.post(f"/api/v1/resumes/{resume_id}/parse").status_code == 200
    assert client.post(f"/api/v1/jobs/{job_description_id}/parse").status_code == 200

    package_response = client.post(
        "/api/v1/prep-packages",
        json={
            "resume_id": resume_id,
            "job_description_id": job_description_id,
            "preparation_goal": case["preparation_goal"],
        },
    )
    assert package_response.status_code == 200
    prep_package_id = package_response.json()["data"]["prep_package_id"]

    questions_response = client.get(f"/api/v1/prep-packages/{prep_package_id}/questions")
    assert questions_response.status_code == 200
    questions = questions_response.json()["data"]["items"]
    assert len(questions) >= 25

    evaluation_response = client.post(
        "/api/v1/evaluations",
        json={
            "question_db_id": questions[0]["question_db_id"],
            "user_answer": case["user_answer"],
        },
    )
    assert evaluation_response.status_code == 200
    assert 0 <= evaluation_response.json()["data"]["total_score"] <= 100
