from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.db.models.user import utc_now
from app.db.types import JsonDict


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"
    __table_args__ = (
        Index("idx_questions_package_module", "prep_package_id", "module"),
        UniqueConstraint("prep_package_id", "question_id", name="uniq_questions_package_question_id"),
        Index("idx_questions_difficulty", "difficulty"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    prep_package_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("interview_prep_packages.id"), nullable=False
    )
    question_id: Mapped[str] = mapped_column(String(80), nullable=False)
    module: Mapped[str] = mapped_column(String(50), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(50), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_refs_json: Mapped[list] = mapped_column(JsonDict, default=list)
    jd_keywords_json: Mapped[list] = mapped_column(JsonDict, default=list)
    answer_framework: Mapped[str] = mapped_column(Text, nullable=False)
    star_template: Mapped[str] = mapped_column(Text, nullable=False)
    scoring_anchors_json: Mapped[list] = mapped_column(JsonDict, default=list)
    follow_up_questions_json: Mapped[list] = mapped_column(JsonDict, default=list)
    preparation_advice: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RecommendedQuestion(Base):
    __tablename__ = "recommended_questions"
    __table_args__ = (
        UniqueConstraint("prep_package_id", "rank", name="uniq_recommended_package_rank"),
        UniqueConstraint(
            "prep_package_id", "question_db_id", name="uniq_recommended_package_question"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    prep_package_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("interview_prep_packages.id"), nullable=False
    )
    question_db_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("interview_questions.id"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    related_weaknesses_json: Mapped[list] = mapped_column(JsonDict, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

