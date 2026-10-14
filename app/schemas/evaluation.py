from pydantic import Field

from app.schemas.common import AgentOutputMetadata, ScoreItem


class AnswerEvaluation(AgentOutputMetadata):
    question_id: str | None = None
    question_text: str
    user_answer: str
    total_score: float = Field(ge=0, le=100)
    dimension_scores: list[ScoreItem] = Field(min_length=1)
    overall_comment: str
    strengths: list[str]
    improvement_points: list[str] = Field(min_length=1)
    risks: list[str]
    improved_answer: str
    follow_up_questions: list[str] = Field(min_length=1)
    next_practice_suggestion: str
    memory_update: dict
