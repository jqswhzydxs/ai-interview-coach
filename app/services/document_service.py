from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.db.models.source_document import SourceDocument
from app.tools.file_parser import FileParserError, parse_file
from app.tools.text_utils import sha256_text

DocumentType = Literal["resume", "jd", "interview_experience"]


class DocumentService:
    def create_text_document(
        self,
        db: Session,
        *,
        user_id: UUID,
        document_type: DocumentType,
        raw_text: str,
        metadata: dict | None = None,
    ) -> SourceDocument:
        document = SourceDocument(
            user_id=user_id,
            document_type=document_type,
            input_type="text",
            original_filename=None,
            file_path=None,
            raw_text=raw_text,
            text_hash=sha256_text(raw_text),
            metadata_json=metadata or {},
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    def create_upload_document(
        self,
        db: Session,
        *,
        user_id: UUID,
        document_type: DocumentType,
        file: UploadFile,
        metadata: dict | None = None,
    ) -> SourceDocument:
        settings = get_settings()
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)

        original_filename = Path(file.filename or "uploaded.txt").name
        stored_path = upload_dir / f"{uuid4()}_{original_filename}"
        stored_path.write_bytes(file.file.read())

        try:
            parsed = parse_file(stored_path)
        except FileParserError as exc:
            stored_path.unlink(missing_ok=True)
            raise AppError(ErrorCode.VALIDATION_ERROR, str(exc), status_code=422) from exc
        document = SourceDocument(
            user_id=user_id,
            document_type=document_type,
            input_type="upload",
            original_filename=original_filename,
            file_path=str(stored_path),
            raw_text=parsed.text,
            text_hash=sha256_text(parsed.text),
            metadata_json={**(metadata or {}), **parsed.metadata},
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document
