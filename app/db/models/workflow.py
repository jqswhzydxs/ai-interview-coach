from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.db.models.user import utc_now
from app.db.types import JsonDict


class PrepPackageRequest(Base):
    __tablename__ = "prep_package_requests"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    resume_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("resumes.id"), nullable=False)
    job_description_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("job_descriptions.id"), nullable=False
    )
    interview_experience_ids_json: Mapped[list] = mapped_column(JsonDict, default=list)
    preparation_goal: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AnswerSubmission(Base):
    __tablename__ = "answer_submissions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    question_db_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("interview_questions.id"), nullable=True
    )
    custom_question_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_answer: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WorkflowJob(Base):
    __tablename__ = "workflow_jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key_digest", name="uq_workflow_job_idempotency"),
        Index("idx_workflow_jobs_claim", "status", "available_at", "created_at"),
        Index("idx_workflow_jobs_lease", "status", "lease_expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    workflow_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    outcome_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    progress_stage: Mapped[str] = mapped_column(String(80), nullable=False, default="queued")
    progress_current: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    input_resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    input_resource_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    idempotency_key_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    lease_token: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    lease_owner_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    absolute_deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    safe_failure_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    safe_failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    agent_run_ids_json: Mapped[list] = mapped_column(JsonDict, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class WorkflowJobAttempt(Base):
    __tablename__ = "workflow_job_attempts"
    __table_args__ = (
        UniqueConstraint("workflow_job_id", "attempt_number", name="uq_workflow_attempt_number"),
        Index("idx_workflow_attempts_job", "workflow_job_id", "attempt_number"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workflow_job_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("workflow_jobs.id", ondelete="CASCADE"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lease_token: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    failure_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    provider_call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    successful_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    successful_total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    billing_usage_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkflowJobStage(Base):
    __tablename__ = "workflow_job_stages"
    __table_args__ = (
        UniqueConstraint("workflow_job_id", "stage_key", name="uq_workflow_stage_key"),
        Index("idx_workflow_stages_job_order", "workflow_job_id", "stage_order"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workflow_job_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("workflow_jobs.id", ondelete="CASCADE"), nullable=False
    )
    stable_stage_id: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    stage_key: Mapped[str] = mapped_column(String(80), nullable=False)
    stage_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    external_effect_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="not_started"
    )
    agent_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("agent_runs.id"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkflowJobResult(Base):
    __tablename__ = "workflow_job_results"
    __table_args__ = (
        UniqueConstraint("workflow_job_id", "relation", name="uq_workflow_result_relation"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workflow_job_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("workflow_jobs.id", ondelete="CASCADE"), nullable=False
    )
    relation: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    resource_href: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
