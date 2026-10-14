from uuid import UUID

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db import session as db_session
from app.db.models.user import User
from app.main import create_app


def test_app_startup_creates_default_user_once(tmp_path, monkeypatch) -> None:
    default_user_id = UUID("00000000-0000-0000-0000-000000000099")
    database_url = f"sqlite+pysqlite:///{tmp_path / 'default_user.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DEFAULT_USER_ID", str(default_user_id))
    get_settings.cache_clear()

    command.upgrade(Config("alembic.ini"), "head")

    app = create_app()
    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200

    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200

    with db_session.SessionLocal() as session:
        users = session.scalars(select(User).where(User.id == default_user_id)).all()

    assert len(users) == 1
    assert users[0].role == "candidate"
    assert users[0].display_name == "Default Candidate"


def teardown_function() -> None:
    get_settings.cache_clear()
