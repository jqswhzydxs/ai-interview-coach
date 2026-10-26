from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


WorkflowType = Literal[
    "resume_parse",
    "job_description_parse",
    "interview_experience_parse",
    "prep_package_generation",
    "answer_evaluation",
]
WorkflowStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class PrepPackageRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resume_id: UUID
    job_description_id: UUID
    interview_experience_ids: list[UUID] = Field(default_factory=list)
    preparation_goal: str = Field(min_length=1, max_length=500)
    title: str | None = Field(default=None, max_length=200)


class PrepPackageRequestCreated(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prep_package_request_id: UUID
    created_at: datetime


class AnswerSubmissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_db_id: UUID | None = None
    custom_question_text: str | None = Field(default=None, min_length=1, max_length=500)
    user_answer: str = Field(min_length=1, max_length=50_000)

    @model_validator(mode="after")
    def exactly_one_question_source(self) -> "AnswerSubmissionCreate":
        if (self.question_db_id is None) == (self.custom_question_text is None):
            raise ValueError("exactly one of question_db_id or custom_question_text is required")
        return self


class AnswerSubmissionCreated(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer_submission_id: UUID
    created_at: datetime


class WorkflowInputResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource_type: Literal[
        "resume",
        "job_description",
        "interview_experience",
        "prep_package_request",
        "answer_submission",
    ]
    resource_id: UUID


class WorkflowJobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_type: WorkflowType
    input_resource: WorkflowInputResource

    @model_validator(mode="after")
    def matching_resource_type(self) -> "WorkflowJobCreate":
        expected = {
            "resume_parse": "resume",
            "job_description_parse": "job_description",
            "interview_experience_parse": "interview_experience",
            "prep_package_generation": "prep_package_request",
            "answer_evaluation": "answer_submission",
        }[self.workflow_type]
        if self.input_resource.resource_type != expected:
            raise ValueError(f"{self.workflow_type} requires resource_type={expected}")
        return self


class WorkflowStageView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage_id: str
    stage: str
    order: int
    status: Literal["pending", "running", "succeeded", "failed", "cancelled"]
    started_at: datetime | None
    finished_at: datetime | None


class WorkflowResultResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relation: str
    resource_type: str
    resource_id: UUID
    href: str


class SafeFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Literal[
        "validation",
        "not_found",
        "provider",
        "ambiguous_provider_outcome",
        "deadline",
        "attempts_exhausted",
        "internal",
    ]
    code: str


class WorkflowJobView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_job_id: UUID
    workflow_type: WorkflowType
    status: WorkflowStatus
    outcome_mode: Literal["standard", "degraded"] | None
    progress_stage: str
    progress_current: int
    progress_total: int
    attempt_count: int
    cancel_requested: bool
    safe_failure: SafeFailure | None
    result_resources: list[WorkflowResultResource]
    agent_run_ids: list[UUID]
    stages: list[WorkflowStageView]
    created_at: datetime
    started_at: datetime | None
    heartbeat_at: datetime | None
    finished_at: datetime | None


class WorkflowSuccessEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: WorkflowJobView
    message: str
    request_id: str


class PrepPackageRequestEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: PrepPackageRequestCreated
    message: str
    request_id: str


class AnswerSubmissionEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: AnswerSubmissionCreated
    message: str
    request_id: str
