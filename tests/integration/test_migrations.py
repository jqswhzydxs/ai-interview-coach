from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import get_settings


def test_initial_migration_creates_mvp_tables(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    assert "alembic_version" in tables
    assert {
        "users",
        "source_documents",
        "resumes",
        "resume_profiles",
        "job_descriptions",
        "jd_profiles",
        "interview_experiences",
        "experience_profiles",
        "agent_runs",
        "agent_run_steps",
        "interview_prep_packages",
        "prep_package_experiences",
        "match_reports",
        "interview_questions",
        "recommended_questions",
        "answer_evaluations",
        "memory_items",
    }.issubset(tables)
    assert "interview_reviews" not in tables
    assert "quality_evaluations" not in tables


def teardown_function() -> None:
    get_settings.cache_clear()
