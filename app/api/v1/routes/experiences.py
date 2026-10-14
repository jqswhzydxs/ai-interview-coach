from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.deps import get_db
from app.services.experience_service import ExperienceService
from app.schemas.response import success_response


router = APIRouter(prefix="/experiences")


class ExperienceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_document_id: UUID
    title: str = Field(min_length=1, max_length=200)
    experience_type: str = Field(min_length=1, max_length=50)
    company_name: str | None = None
    role_name: str | None = None


def serialize_experience(experience) -> dict:
    return {
        "interview_experience_id": experience.id,
        "source_document_id": experience.source_document_id,
        "title": experience.title,
        "experience_type": experience.experience_type,
        "company_name": experience.company_name,
        "role_name": experience.role_name,
        "created_at": experience.created_at,
    }


@router.post("")
def create_experience(
    payload: ExperienceCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    experience = ExperienceService().create_experience(
        db,
        user_id=get_settings().default_user_id,
        source_document_id=payload.source_document_id,
        title=payload.title,
        experience_type=payload.experience_type,
        company_name=payload.company_name,
        role_name=payload.role_name,
    )
    return success_response(serialize_experience(experience), request.state.request_id)


@router.post("/{interview_experience_id}/parse")
async def parse_experience(
    interview_experience_id: UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    profile, agent_run_id = await ExperienceService().parse_experience(
        db, interview_experience_id=interview_experience_id
    )
    return success_response(
        {
            "interview_experience_id": profile.interview_experience_id,
            "experience_profile_id": profile.id,
            "agent_run_id": agent_run_id,
        },
        request.state.request_id,
    )
