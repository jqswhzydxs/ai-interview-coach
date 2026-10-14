from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.db.models.user import utc_now
from app.db.types import JsonDict


class InterviewPrepPackage(Base):
    __tablename__ = "interview_prep_packages"
    __table_args__ = (
        Index("idx_prep_packages_user_created", "user_id", "created_at"),
        Index("idx_prep_packages_resume_jd", "resume_id", "job_description_id"),
        Index("idx_prep_packages_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    resume_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("resumes.id"), nullable=False)
    resume_profile_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("resume_profiles.id"), nullable=False
    )
    job_description_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("job_descriptions.id"), nullable=False
    )
    jd_profile_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("jd_profiles.id"), nullable=False)
    agent_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("agent_runs.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    package_version: Mapped[str] = mapped_column(String(50), nullable=False)
    overview_json: Mapped[dict] = mapped_column(JsonDict, default=dict)
    priority_plan_json: Mapped[dict] = mapped_column(JsonDict, default=dict)
    action_items_json: Mapped[list] = mapped_column(JsonDict, default=list)
    rendered_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class PrepPackageExperience(Base):
    __tablename__ = "prep_package_experiences"
    __table_args__ = (
        UniqueConstraint(
            "prep_package_id", "interview_experience_id", name="uniq_package_experience"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    prep_package_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("interview_prep_packages.id"), nullable=False
    )
    interview_experience_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("interview_experiences.id"), nullable=False
    )
    experience_profile_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("experience_profiles.id"), nullable=True
    )
    relevance_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class MatchReport(Base):
    __tablename__ = "match_reports"
    __table_args__ = (
        Index("idx_match_reports_package", "prep_package_id"),
        Index("idx_match_reports_score", "overall_score"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    prep_package_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("interview_prep_packages.id"), nullable=False
    )
    agent_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("agent_runs.id"), nullable=True
    )
    overall_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    strengths_json: Mapped[list] = mapped_column(JsonDict, default=list)
    gaps_json: Mapped[list] = mapped_column(JsonDict, default=list)
    expression_issues_json: Mapped[list] = mapped_column(JsonDict, default=list)
    risk_points_json: Mapped[list] = mapped_column(JsonDict, default=list)
    resume_suggestions_json: Mapped[list] = mapped_column(JsonDict, default=list)
    evidence_refs_json: Mapped[list] = mapped_column(JsonDict, default=list)
    report_json: Mapped[dict] = mapped_column(JsonDict, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

