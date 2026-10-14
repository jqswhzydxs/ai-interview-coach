from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.db.models.user import utc_now
from app.db.types import JsonDict


class InterviewExperience(Base):
    __tablename__ = "interview_experiences"
    __table_args__ = (
        Index("idx_interview_experiences_user_type", "user_id", "experience_type"),
        Index("idx_interview_experiences_role", "role_name"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    source_document_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("source_documents.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    experience_type: Mapped[str] = mapped_column(String(50), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    role_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ExperienceProfile(Base):
    __tablename__ = "experience_profiles"
    __table_args__ = (
        Index("idx_experience_profiles_exp_created", "interview_experience_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    interview_experience_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("interview_experiences.id"), nullable=False
    )
    agent_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("agent_runs.id"), nullable=True
    )
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    profile_json: Mapped[dict] = mapped_column(JsonDict, default=dict)
    frequent_questions: Mapped[list] = mapped_column(JsonDict, default=list)
    frequent_topics: Mapped[list] = mapped_column(JsonDict, default=list)
    follow_up_patterns: Mapped[list] = mapped_column(JsonDict, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

