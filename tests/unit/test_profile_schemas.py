from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.experience import ExperienceProfile
from app.schemas.job_description import JDProfile
from app.schemas.resume import ResumeProfile


def metadata() -> dict:
    return {
        "schema_version": "v0.1",
        "generated_at": datetime.now(timezone.utc),
        "agent_name": "profile_agent",
        "prompt_version": "profile_agent_v0.1",
    }


def test_resume_profile_accepts_valid_profile() -> None:
    profile = ResumeProfile(
        **metadata(),
        basic_info={"name": "Candidate"},
        education=[{"school": "Example University"}],
        skills=["Python", "FastAPI"],
        projects=[
            {
                "name": "Interview Coach",
                "role": "Backend developer",
                "background": "AI interview preparation",
                "tech_stack": ["FastAPI", "PostgreSQL"],
                "responsibilities": ["API design"],
                "highlights": ["Structured evaluation"],
                "metrics": ["25+ generated questions"],
                "evidence_refs": [{"source_type": "resume", "summary": "Project section"}],
            }
        ],
        work_experiences=[],
        awards=[],
        backend_tags=["api"],
        questionable_points=["Metrics need detail"],
        risk_points=["Project impact is vague"],
    )

    assert profile.projects[0].evidence_refs[0].source_type == "resume"


def test_jd_profile_accepts_valid_profile() -> None:
    profile = JDProfile(
        **metadata(),
        job_title="Backend Engineer",
        company_name="Example Inc",
        job_level=None,
        core_responsibilities=["Build APIs"],
        hard_requirements=["Python"],
        bonus_points=["LLM experience"],
        tech_keywords=["FastAPI"],
        backend_dimensions=["database"],
        interview_focuses=["project depth"],
        evidence_refs=[{"source_type": "jd", "summary": "Requirement section"}],
    )

    assert profile.job_title == "Backend Engineer"


def test_experience_profile_accepts_valid_profile() -> None:
    profile = ExperienceProfile(
        **metadata(),
        source_summary="Backend internship interview notes",
        frequent_questions=["Explain your project"],
        frequent_topics=["API design"],
        follow_up_patterns=["Ask about tradeoffs"],
        jd_related_points=["Python"],
        resume_related_points=["Interview Coach"],
        evidence_refs=[{"source_type": "experience", "summary": "Interview note"}],
    )

    assert profile.frequent_topics == ["API design"]


def test_missing_required_profile_field_fails() -> None:
    payload = {
        **metadata(),
        "education": [],
        "skills": [],
        "projects": [],
        "work_experiences": [],
        "awards": [],
        "backend_tags": [],
        "questionable_points": [],
        "risk_points": [],
    }

    with pytest.raises(ValidationError):
        ResumeProfile(**payload)
