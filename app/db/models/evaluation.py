from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.db.models.user import utc_now
from app.db.types import JsonDict


class AnswerEvaluation(Base):
    __tablename__ = "answer_evaluations"
    __table_args__ = (
        Index("idx_answer_evaluations_user_created", "user_id", "created_at"),
        Index("idx_answer_evaluations_question", "question_db_id"),
        Index("idx_answer_evaluations_total_score", "total_score"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    originating_workflow_job_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("workflow_jobs.id"), nullable=True, unique=True
    )
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    prep_package_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("interview_prep_packages.id"), nullable=True
    )
    question_db_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("interview_questions.id"), nullable=True
    )
    custom_question_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_answer: Mapped[str] = mapped_column(Text, nullable=False)
    agent_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("agent_runs.id"), nullable=True
    )
    evaluation_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="standard"
    )
    score_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_quality: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown"
    )
    source_context_json: Mapped[dict] = mapped_column(JsonDict, default=dict)
    degradation_reasons_json: Mapped[list] = mapped_column(JsonDict, default=list)
    total_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    relevance_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    technical_accuracy_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    project_specificity_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    structure_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    communication_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    risk_control_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    strengths_json: Mapped[list] = mapped_column(JsonDict, default=list)
    improvement_points_json: Mapped[list] = mapped_column(JsonDict, default=list)
    risks_json: Mapped[list] = mapped_column(JsonDict, default=list)
    improved_answer: Mapped[str] = mapped_column(Text, nullable=False)
    follow_up_questions_json: Mapped[list] = mapped_column(JsonDict, default=list)
    next_practice_suggestion: Mapped[str] = mapped_column(Text, nullable=False)
    memory_update_json: Mapped[dict] = mapped_column(JsonDict, default=dict)
    evaluation_json: Mapped[dict] = mapped_column(JsonDict, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
