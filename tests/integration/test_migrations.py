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
    agent_run_columns = {column["name"] for column in inspector.get_columns("agent_runs")}
    evaluation_columns = {
        column["name"]: column
        for column in inspector.get_columns("answer_evaluations")
    }

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
    assert {
        "provider",
        "execution_mode",
        "real_call_count",
        "retry_count",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "fallback_reason_json",
        "failure_counts_json",
    }.issubset(agent_run_columns)
    assert {
        "evaluation_mode",
        "score_available",
        "source_quality",
        "source_context_json",
        "degradation_reasons_json",
    }.issubset(evaluation_columns)
    assert evaluation_columns["total_score"]["nullable"] is True
    assert evaluation_columns["relevance_score"]["nullable"] is True


def test_llm_observability_migration_upgrades_and_downgrades(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'observability_migration.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config("alembic.ini")

    command.upgrade(config, "9c8951c88817")
    engine = create_engine(database_url)
    initial_columns = {column["name"] for column in inspect(engine).get_columns("agent_runs")}
    assert "execution_mode" not in initial_columns
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    upgraded_columns = {column["name"] for column in inspect(engine).get_columns("agent_runs")}
    assert "execution_mode" in upgraded_columns
    assert "fallback_reason_json" in upgraded_columns
    engine.dispose()

    command.downgrade(config, "9c8951c88817")
    engine = create_engine(database_url)
    downgraded_columns = {column["name"] for column in inspect(engine).get_columns("agent_runs")}
    assert "execution_mode" not in downgraded_columns
    assert "fallback_reason_json" not in downgraded_columns
    engine.dispose()


def test_degraded_evaluation_migration_round_trip(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'degraded_migration.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config("alembic.ini")

    command.upgrade(config, "a61f2b3c4d5e")
    engine = create_engine(database_url)
    before = {
        column["name"]: column
        for column in inspect(engine).get_columns("answer_evaluations")
    }
    assert "evaluation_mode" not in before
    assert before["total_score"]["nullable"] is False
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    upgraded = {
        column["name"]: column
        for column in inspect(engine).get_columns("answer_evaluations")
    }
    assert upgraded["evaluation_mode"]["nullable"] is False
    assert upgraded["score_available"]["nullable"] is False
    assert upgraded["total_score"]["nullable"] is True
    engine.dispose()

    command.downgrade(config, "a61f2b3c4d5e")
    engine = create_engine(database_url)
    downgraded = {
        column["name"]: column
        for column in inspect(engine).get_columns("answer_evaluations")
    }
    assert "evaluation_mode" not in downgraded
    assert downgraded["total_score"]["nullable"] is False
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    assert "evaluation_mode" in {
        column["name"]
        for column in inspect(engine).get_columns("answer_evaluations")
    }
    engine.dispose()


def teardown_function() -> None:
    get_settings.cache_clear()
