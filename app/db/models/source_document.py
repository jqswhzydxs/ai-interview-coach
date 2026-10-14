from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.db.models.user import utc_now
from app.db.types import JsonDict


class SourceDocument(Base):
    __tablename__ = "source_documents"
    __table_args__ = (
        Index("idx_source_documents_user_type", "user_id", "document_type"),
        Index("idx_source_documents_text_hash", "text_hash"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    input_type: Mapped[str] = mapped_column(String(50), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JsonDict, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

