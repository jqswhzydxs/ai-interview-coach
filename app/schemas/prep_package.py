from pydantic import Field

from app.schemas.common import ActionItem, AgentOutputMetadata, EvidenceRef, StrictBaseModel
from app.schemas.question import QuestionBank


class ResumeSuggestion(StrictBaseModel):
    target_section: str
    problem: str
    suggestion: str
    example_rewrite: str
    evidence_refs: list[EvidenceRef]


class MatchReport(AgentOutputMetadata):
    overall_score: float = Field(ge=0, le=100)
    summary: str
    matched_strengths: list[str]
    missing_capabilities: list[str]
    expression_issues: list[str]
    risk_points: list[str]
    resume_suggestions: list[ResumeSuggestion]
    preparation_priorities: list[str]
    evidence_refs: list[EvidenceRef]


class RecommendedQuestion(StrictBaseModel):
    question_id: str
    rank: int = Field(ge=1)
    reason: str
    related_weaknesses: list[str]


class InterviewPrepPackage(AgentOutputMetadata):
    overview: dict
    jd_breakdown: dict
    match_report: MatchReport
    resume_suggestions: list[ResumeSuggestion]
    preparation_priorities: list[ActionItem]
    question_bank: QuestionBank
    recommended_questions: list[RecommendedQuestion]
    action_items: list[ActionItem]
    rendered_markdown: str | None = None
