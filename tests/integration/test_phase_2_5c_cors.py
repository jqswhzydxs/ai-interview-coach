from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture()
def cors_client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'cors.db'}")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://127.0.0.1:4173")
    monkeypatch.setenv("CORS_ALLOW_CREDENTIALS", "false")
    get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")
    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()


def test_cors_allows_only_configured_origin_without_credentials(cors_client) -> None:
    response = cors_client.get(
        "/api/v1/health",
        headers={"origin": "http://127.0.0.1:4173"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:4173"
    assert "access-control-allow-credentials" not in response.headers


def test_cors_rejects_unconfigured_origin(cors_client) -> None:
    response = cors_client.get(
        "/api/v1/health",
        headers={"origin": "http://127.0.0.1:9999"},
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_cors_preflight_is_exact(cors_client) -> None:
    allowed = cors_client.options(
        "/api/v1/documents/text",
        headers={
            "origin": "http://127.0.0.1:4173",
            "access-control-request-method": "POST",
            "access-control-request-headers": "content-type,x-request-id",
        },
    )
    denied = cors_client.options(
        "/api/v1/documents/text",
        headers={
            "origin": "https://unconfigured.invalid",
            "access-control-request-method": "POST",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:4173"
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


def test_cors_wildcard_configuration_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="wildcard"):
            create_app()
    finally:
        get_settings.cache_clear()
