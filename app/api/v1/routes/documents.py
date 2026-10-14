from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.deps import get_db
from app.services.document_service import DocumentService, DocumentType
from app.schemas.response import success_response


router = APIRouter(prefix="/documents")


class TextDocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType
    raw_text: str = Field(min_length=1)
    metadata: dict | None = None


def serialize_document(document) -> dict:
    return {
        "source_document_id": document.id,
        "document_type": document.document_type,
        "input_type": document.input_type,
        "original_filename": document.original_filename,
        "file_path": document.file_path,
        "text_hash": document.text_hash,
        "metadata": document.metadata_json,
        "created_at": document.created_at,
    }


@router.post("/text")
def create_text_document(
    payload: TextDocumentCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    document = DocumentService().create_text_document(
        db,
        user_id=get_settings().default_user_id,
        document_type=payload.document_type,
        raw_text=payload.raw_text,
        metadata=payload.metadata,
    )
    return success_response(serialize_document(document), request.state.request_id)


@router.post("/upload")
def upload_document(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    document_type: Annotated[DocumentType, Form()],
    file: Annotated[UploadFile, File()],
) -> dict:
    document = DocumentService().create_upload_document(
        db,
        user_id=get_settings().default_user_id,
        document_type=document_type,
        file=file,
    )
    return success_response(serialize_document(document), request.state.request_id)
