from collections.abc import Iterator
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.models.source_document import SourceDocument
from app.main import create_app
from app.tools.text_utils import sha256_text


@pytest.fixture()
def client_and_session(tmp_path, monkeypatch) -> Iterator[tuple[TestClient, sessionmaker]]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'documents.db'}"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")

    app = create_app()
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with TestClient(app) as client:
        yield client, SessionLocal

    get_settings.cache_clear()


def test_create_text_resume_document(client_and_session) -> None:
    client, SessionLocal = client_and_session

    response = client.post(
        "/api/v1/documents/text",
        json={
            "document_type": "resume",
            "raw_text": "Backend developer resume",
            "metadata": {"title": "Resume v1"},
        },
        headers={"x-request-id": "doc-text-1"},
    )

    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert body["request_id"] == "doc-text-1"
    assert data["document_type"] == "resume"
    assert data["input_type"] == "text"
    assert data["text_hash"] == sha256_text("Backend developer resume")

    with SessionLocal() as session:
        document = session.get(SourceDocument, UUID(data["source_document_id"]))

    assert document.raw_text == "Backend developer resume"
    assert document.metadata_json == {"title": "Resume v1"}


@pytest.mark.parametrize("document_type", ["jd", "interview_experience"])
def test_create_text_document_supported_types(client_and_session, document_type: str) -> None:
    client, SessionLocal = client_and_session

    response = client.post(
        "/api/v1/documents/text",
        json={"document_type": document_type, "raw_text": "Useful material"},
    )

    assert response.status_code == 200
    data = response.json()["data"]

    with SessionLocal() as session:
        document = session.scalars(
            select(SourceDocument).where(SourceDocument.id == UUID(data["source_document_id"]))
        ).one()

    assert document.document_type == document_type
    assert document.raw_text == "Useful material"


def test_upload_text_file_is_saved_and_parsed(client_and_session) -> None:
    client, SessionLocal = client_and_session

    response = client.post(
        "/api/v1/documents/upload",
        data={"document_type": "resume"},
        files={"file": ("resume.txt", b"Uploaded resume text", "text/plain")},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["input_type"] == "upload"
    assert data["original_filename"] == "resume.txt"

    with SessionLocal() as session:
        document = session.get(SourceDocument, UUID(data["source_document_id"]))

    assert document.raw_text == "Uploaded resume text"
    assert document.file_path is not None


def test_upload_unsupported_file_type_returns_validation_error(client_and_session) -> None:
    client, _ = client_and_session

    response = client.post(
        "/api/v1/documents/upload",
        data={"document_type": "resume"},
        files={"file": ("resume.exe", b"nope", "application/octet-stream")},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "File extension is not allowed"
    assert list(get_settings().upload_dir.glob("*")) == []


def test_upload_over_10_mib_file_returns_validation_error(client_and_session) -> None:
    client, _ = client_and_session

    response = client.post(
        "/api/v1/documents/upload",
        data={"document_type": "resume"},
        files={"file": ("resume.txt", b"0" * (10 * 1024 * 1024 + 1), "text/plain")},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "File exceeds upload size limit"
    assert list(get_settings().upload_dir.glob("*")) == []


def test_upload_rejects_mime_mismatch_without_residual_file(client_and_session) -> None:
    client, _ = client_and_session

    response = client.post(
        "/api/v1/documents/upload",
        data={"document_type": "resume"},
        files={"file": ("resume.txt", b"safe text", "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["message"] == "File content type is not allowed"
    assert list(get_settings().upload_dir.glob("*")) == []


def test_upload_rejects_signature_mismatch_without_echoing_content(
    client_and_session,
) -> None:
    client, _ = client_and_session
    marker = "private-marker-must-not-be-echoed"

    response = client.post(
        "/api/v1/documents/upload",
        data={"document_type": "resume"},
        files={"file": ("resume.pdf", marker.encode(), "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["message"] == "File content does not match its extension"
    assert marker not in response.text
    assert list(get_settings().upload_dir.glob("*")) == []


def test_invalid_document_type_returns_validation_error(client_and_session) -> None:
    client, _ = client_and_session

    response = client.post(
        "/api/v1/documents/text",
        json={"document_type": "cover_letter", "raw_text": "not supported"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
