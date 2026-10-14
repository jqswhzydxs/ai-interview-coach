from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.deps import get_db
from app.db.session import create_db_engine


def test_create_db_engine_uses_provided_url() -> None:
    engine = create_db_engine("sqlite+pysqlite:///:memory:")

    assert engine.url.drivername == "sqlite+pysqlite"
    assert engine.url.database == ":memory:"


def test_base_metadata_is_available() -> None:
    assert Base.metadata is not None


def test_get_db_yields_session() -> None:
    dependency = get_db()
    db = next(dependency)

    try:
        assert isinstance(db, Session)
    finally:
        try:
            next(dependency)
        except StopIteration:
            pass
