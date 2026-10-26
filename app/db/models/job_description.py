from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.db.models.user import utc_now
from app.db.types import JsonDict


class JobDescription(Base):
    __tablename__ = "job_descriptions"
    __table_args__ = (
        Index("idx_job_descriptions_user_created", "user_id", "created_at"),
        Index("idx_job_descriptions_direction", "target_direction"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    source_document_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("source_documents.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    job_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    target_direction: Mapped[str] = mapped_column(String(100), default="backend")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class JDProfile(Base):
    __tablename__ = "jd_profiles"
    __table_args__ = (Index("idx_jd_profiles_jd_created", "job_description_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    originating_workflow_job_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("workflow_jobs.id"), nullable=True, unique=True
    )
    job_description_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("job_descriptions.id"), nullable=False
    )
    agent_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("agent_runs.id"), nullable=True
    )
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    profile_json: Mapped[dict] = mapped_column(JsonDict, default=dict)
    core_responsibilities: Mapped[list] = mapped_column(JsonDict, default=list)
    hard_requirements: Mapped[list] = mapped_column(JsonDict, default=list)
    bonus_points: Mapped[list] = mapped_column(JsonDict, default=list)
    tech_keywords: Mapped[list] = mapped_column(JsonDict, default=list)
    backend_dimensions: Mapped[list] = mapped_column(JsonDict, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

