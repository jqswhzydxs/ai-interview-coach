from datetime import datetime, timezone

from app.schemas.prep_package import InterviewPrepPackage, MatchReport, RecommendedQuestion
from tests.unit.test_question_bank_schemas import make_question_bank


def metadata() -> dict:
    return {
        "schema_version": "v0.1",
        "generated_at": datetime.now(timezone.utc),
        "agent_name": "prep_package_agent",
        "prompt_version": "prep_package_agent_v0.1",
    }


def test_match_report_accepts_valid_report() -> None:
    report = MatchReport(
        **metadata(),
        overall_score=82,
        summary="Good backend fit with project depth gaps",
        matched_strengths=["FastAPI experience"],
        missing_capabilities=["System design depth"],
        expression_issues=["Needs metrics"],
        risk_points=["Vague project impact"],
        resume_suggestions=[
            {
                "target_section": "projects",
                "problem": "Missing metrics",
                "suggestion": "Add latency or throughput numbers",
                "example_rewrite": "Reduced p95 latency by 20%",
                "evidence_refs": [{"source_type": "resume", "summary": "Project section"}],
            }
        ],
        preparation_priorities=["Project depth"],
        evidence_refs=[{"source_type": "jd", "summary": "Backend requirement"}],
    )

    assert report.overall_score == 82


def test_interview_prep_package_accepts_valid_package() -> None:
    package = InterviewPrepPackage(
        **metadata(),
        overview={"goal": "Backend interview preparation"},
        jd_breakdown={"focus": "API and database"},
        match_report={
            **metadata(),
            "overall_score": 82,
            "summary": "Good fit",
            "matched_strengths": ["FastAPI"],
            "missing_capabilities": ["System design"],
            "expression_issues": ["Metrics"],
            "risk_points": ["Depth"],
            "resume_suggestions": [],
            "preparation_priorities": ["Project depth"],
            "evidence_refs": [{"source_type": "jd", "summary": "Requirement"}],
        },
        resume_suggestions=[],
        preparation_priorities=[
            {"title": "Project review", "priority": "high", "description": "Prepare STAR stories"}
        ],
        question_bank=make_question_bank().model_dump(),
        recommended_questions=[
            {"question_id": "self-0", "rank": 1, "reason": "Warm-up", "related_weaknesses": []},
            {"question_id": "pro-0", "rank": 2, "reason": "Core skill", "related_weaknesses": []},
            {"question_id": "beh-0", "rank": 3, "reason": "Project depth", "related_weaknesses": []},
        ],
        action_items=[
            {"title": "Refine metrics", "priority": "medium", "description": "Add concrete numbers"}
        ],
        rendered_markdown=None,
    )

    assert len(package.recommended_questions) == 3


def test_recommended_question_rank_must_be_positive() -> None:
    from pydantic import ValidationError
    import pytest

    with pytest.raises(ValidationError):
        RecommendedQuestion(question_id="self-0", rank=0, reason="invalid", related_weaknesses=[])
