from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import EvidenceRef, StrictBaseModel


MemoryType = Literal["weakness", "strength", "preference", "target_role", "project_pattern"]
MemorySourceType = Literal["answer_evaluation", "interview_review", "user_feedback", "manual"]
MemoryStatus = Literal["active", "archived", "rejected"]


class MemoryItem(StrictBaseModel):
    memory_type: MemoryType
    category: str
    content: str
    evidence: list[EvidenceRef] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    source_type: MemorySourceType
    source_id: UUID | None = None
    status: MemoryStatus


class MemoryUpdate(StrictBaseModel):
    write_decision: Literal["write", "skip"] = "write"
    skip_reason: dict | None = None
    memory_items: list[MemoryItem]

    @model_validator(mode="after")
    def validate_write_decision(self) -> "MemoryUpdate":
        if self.write_decision == "write":
            if not self.memory_items:
                raise ValueError("write decision requires at least one memory item")
            if self.skip_reason is not None:
                raise ValueError("write decision cannot include skip_reason")
        else:
            if self.memory_items:
                raise ValueError("skip decision cannot include memory items")
            if not self.skip_reason:
                raise ValueError("skip decision requires skip_reason")
        return self
