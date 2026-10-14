from app.db.base import Base, import_models


def test_mvp_tables_are_registered() -> None:
    import_models()

    expected_tables = {
        "users",
        "source_documents",
        "resumes",
        "resume_profiles",
        "job_descriptions",
        "jd_profiles",
        "interview_experiences",
        "experience_profiles",
        "interview_prep_packages",
        "prep_package_experiences",
        "match_reports",
        "interview_questions",
        "recommended_questions",
        "answer_evaluations",
        "memory_items",
        "agent_runs",
        "agent_run_steps",
    }

    assert expected_tables.issubset(set(Base.metadata.tables))


def test_deferred_tables_are_not_registered() -> None:
    import_models()

    assert "interview_reviews" not in Base.metadata.tables
    assert "quality_evaluations" not in Base.metadata.tables


def test_core_constraints_are_registered() -> None:
    import_models()

    interview_questions = Base.metadata.tables["interview_questions"]
    constraint_names = {constraint.name for constraint in interview_questions.constraints}
    assert "uniq_questions_package_question_id" in constraint_names

    recommended_questions = Base.metadata.tables["recommended_questions"]
    recommended_constraint_names = {
        constraint.name for constraint in recommended_questions.constraints
    }
    assert "uniq_recommended_package_rank" in recommended_constraint_names
    assert "uniq_recommended_package_question" in recommended_constraint_names

