from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.deps import get_db
from app.services.resume_service import ResumeService
from app.schemas.response import success_response


router = APIRouter(prefix="/resumes")


class ResumeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_document_id: UUID
    title: str = Field(min_length=1, max_length=200)
    target_direction: str | None = None
    version_label: str | None = None


def serialize_resume(resume) -> dict:
    return {
        "resume_id": resume.id,
        "source_document_id": resume.source_document_id,
        "title": resume.title,
        "target_direction": resume.target_direction,
        "version_label": resume.version_label,
        "is_active": resume.is_active,
        "created_at": resume.created_at,
    }


@router.post("")
def create_resume(
    payload: ResumeCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    resume = ResumeService().create_resume(
        db,
        user_id=get_settings().default_user_id,
        source_document_id=payload.source_document_id,
        title=payload.title,
        target_direction=payload.target_direction,
        version_label=payload.version_label,
    )
    return success_response(serialize_resume(resume), request.state.request_id)


@router.post("/{resume_id}/parse")
async def parse_resume(
    resume_id: UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    profile, agent_run_id = await ResumeService().parse_resume(db, resume_id=resume_id)
    return success_response(
        {
            "resume_id": profile.resume_id,
            "resume_profile_id": profile.id,
            "agent_run_id": agent_run_id,
        },
        request.state.request_id,
    )
