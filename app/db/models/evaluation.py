from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, Text
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
    total_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    relevance_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    technical_accuracy_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    project_specificity_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    structure_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    communication_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    risk_control_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    strengths_json: Mapped[list] = mapped_column(JsonDict, default=list)
    improvement_points_json: Mapped[list] = mapped_column(JsonDict, default=list)
    risks_json: Mapped[list] = mapped_column(JsonDict, default=list)
    improved_answer: Mapped[str] = mapped_column(Text, nullable=False)
    follow_up_questions_json: Mapped[list] = mapped_column(JsonDict, default=list)
    next_practice_suggestion: Mapped[str] = mapped_column(Text, nullable=False)
    memory_update_json: Mapped[dict] = mapped_column(JsonDict, default=dict)
    evaluation_json: Mapped[dict] = mapped_column(JsonDict, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

