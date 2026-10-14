from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import StrictBaseModel


AgentRunStatus = Literal["pending", "running", "succeeded", "failed"]


class AgentRunStepResponse(StrictBaseModel):
    id: UUID
    step_order: int = Field(ge=1)
    agent_name: str
    action_type: str
    status: AgentRunStatus
    error_message: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    created_at: datetime


class AgentRunResponse(StrictBaseModel):
    id: UUID
    run_type: str
    status: AgentRunStatus
    prompt_version: str | None = None
    steps: list[AgentRunStepResponse]
    error_message: str | None = None
    created_at: datetime

    @model_validator(mode="after")
    def sort_steps_by_order(self) -> "AgentRunResponse":
        self.steps = sorted(self.steps, key=lambda step: step.step_order)
        return self
