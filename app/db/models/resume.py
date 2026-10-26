from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.db.models.user import utc_now
from app.db.types import JsonDict


class Resume(Base):
    __tablename__ = "resumes"
    __table_args__ = (Index("idx_resumes_user_active", "user_id", "is_active"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    source_document_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("source_documents.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    target_direction: Mapped[str | None] = mapped_column(String(100), nullable=True)
    version_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ResumeProfile(Base):
    __tablename__ = "resume_profiles"
    __table_args__ = (
        Index("idx_resume_profiles_resume_created", "resume_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    originating_workflow_job_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("workflow_jobs.id"), nullable=True, unique=True
    )
    resume_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("resumes.id"), nullable=False)
    agent_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("agent_runs.id"), nullable=True
    )
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    profile_json: Mapped[dict] = mapped_column(JsonDict, default=dict)
    skills: Mapped[list] = mapped_column(JsonDict, default=list)
    projects: Mapped[list] = mapped_column(JsonDict, default=list)
    backend_tags: Mapped[list] = mapped_column(JsonDict, default=list)
    risk_points: Mapped[list] = mapped_column(JsonDict, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

