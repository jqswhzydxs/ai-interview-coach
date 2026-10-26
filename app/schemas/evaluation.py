from typing import Literal

from pydantic import Field, model_validator

from app.schemas.common import AgentOutputMetadata, ScoreItem


class AnswerEvaluation(AgentOutputMetadata):
    evaluation_mode: Literal["standard", "degraded"] = "standard"
    score_available: bool = True
    source_quality: Literal[
        "trusted", "synthetic", "degraded", "user_provided", "mixed", "unknown"
    ] = "unknown"
    degradation_reasons: list[str] = Field(default_factory=list)
    question_id: str | None = None
    question_text: str
    user_answer: str
    total_score: float | None = Field(default=None, ge=0, le=100)
    dimension_scores: list[ScoreItem]
    overall_comment: str
    strengths: list[str]
    improvement_points: list[str] = Field(min_length=1)
    risks: list[str]
    improved_answer: str
    follow_up_questions: list[str] = Field(min_length=1)
    next_practice_suggestion: str
    memory_update: dict

    @model_validator(mode="after")
    def validate_evaluation_mode(self) -> "AnswerEvaluation":
        if self.evaluation_mode == "standard":
            if not self.score_available:
                raise ValueError("standard evaluation must make its score available")
            if self.total_score is None:
                raise ValueError("standard evaluation requires total_score")
            if not self.dimension_scores:
                raise ValueError("standard evaluation requires dimension_scores")
            if self.degradation_reasons:
                raise ValueError("standard evaluation cannot have degradation_reasons")
        else:
            if self.score_available:
                raise ValueError("degraded evaluation cannot make a score available")
            if self.total_score is not None:
                raise ValueError("degraded evaluation cannot contain total_score")
            if self.dimension_scores:
                raise ValueError("degraded evaluation cannot contain dimension_scores")
            if not self.degradation_reasons:
                raise ValueError("degraded evaluation requires degradation_reasons")
            if self.source_quality != "degraded":
                raise ValueError("degraded evaluation requires degraded source_quality")
        return self
