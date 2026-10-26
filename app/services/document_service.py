from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.core.http_policy import get_http_policy_settings
from app.db.models.source_document import SourceDocument
from app.tools.file_parser import parse_file
from app.tools.text_utils import sha256_text

DocumentType = Literal["resume", "jd", "interview_experience"]
UPLOAD_CHUNK_SIZE = 64 * 1024
ALLOWED_UPLOAD_CONTENT_TYPES = {
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    },
    ".txt": {"text/plain"},
}


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
        upload_max_bytes = get_http_policy_settings().upload_max_bytes
        upload_dir = Path(settings.upload_dir)
        original_filename = Path(file.filename or "uploaded.txt").name
        suffix = Path(original_filename).suffix.lower()
        content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
        if suffix not in ALLOWED_UPLOAD_CONTENT_TYPES:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "File extension is not allowed",
                status_code=422,
            )
        if content_type not in ALLOWED_UPLOAD_CONTENT_TYPES[suffix]:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "File content type is not allowed",
                status_code=422,
            )

        upload_dir.mkdir(parents=True, exist_ok=True)
        stored_path = upload_dir / f"{uuid4()}_{original_filename}"
        try:
            total_bytes = 0
            with stored_path.open("wb") as target:
                while chunk := file.file.read(UPLOAD_CHUNK_SIZE):
                    total_bytes += len(chunk)
                    if total_bytes > upload_max_bytes:
                        raise AppError(
                            ErrorCode.VALIDATION_ERROR,
                            "File exceeds upload size limit",
                            status_code=422,
                        )
                    target.write(chunk)
            self._validate_file_signature(stored_path, suffix)
            try:
                parsed = parse_file(
                    stored_path,
                    max_size_bytes=upload_max_bytes,
                )
            except Exception as exc:
                raise AppError(
                    ErrorCode.VALIDATION_ERROR,
                    "File content could not be safely parsed",
                    status_code=422,
                ) from exc
            if not parsed.text.strip():
                raise AppError(
                    ErrorCode.VALIDATION_ERROR,
                    "File contains no readable text",
                    status_code=422,
                )
        except Exception:
            stored_path.unlink(missing_ok=True)
            raise
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
        try:
            db.add(document)
            db.commit()
            db.refresh(document)
        except Exception:
            db.rollback()
            stored_path.unlink(missing_ok=True)
            raise
        return document

    def _validate_file_signature(self, path: Path, suffix: str) -> None:
        with path.open("rb") as source:
            prefix = source.read(8)
        valid = (
            (suffix == ".pdf" and prefix.startswith(b"%PDF-"))
            or (suffix == ".docx" and prefix.startswith(b"PK\x03\x04"))
            or (suffix == ".txt" and b"\x00" not in prefix)
        )
        if not valid:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "File content does not match its extension",
                status_code=422,
            )
