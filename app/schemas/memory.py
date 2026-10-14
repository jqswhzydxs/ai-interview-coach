from typing import Literal
from uuid import UUID

from pydantic import Field

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
