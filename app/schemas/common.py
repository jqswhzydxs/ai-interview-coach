from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


EvidenceSourceType = Literal["resume", "jd", "experience", "answer", "inferred"]
Priority = Literal["high", "medium", "low"]


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceRef(StrictBaseModel):
    source_type: EvidenceSourceType
    source_id: UUID | None = None
    quote: str | None = None
    summary: str


class ScoreItem(StrictBaseModel):
    name: str
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    reason: str

    @model_validator(mode="after")
    def validate_score_within_max(self) -> "ScoreItem":
        if self.score > self.max_score:
            raise ValueError("score must be less than or equal to max_score")
        return self


class ActionItem(StrictBaseModel):
    title: str
    priority: Priority
    description: str
    expected_time: str | None = None


class AgentOutputMetadata(StrictBaseModel):
    schema_version: str
    generated_at: datetime
    agent_name: str
    prompt_version: str
