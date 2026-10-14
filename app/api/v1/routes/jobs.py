from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.deps import get_db
from app.services.job_service import JobService
from app.schemas.response import success_response


router = APIRouter(prefix="/jobs")


class JobDescriptionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_document_id: UUID
    title: str = Field(min_length=1, max_length=200)
    company_name: str | None = None
    job_url: str | None = None
    target_direction: str = "backend"


def serialize_job(job) -> dict:
    return {
        "job_description_id": job.id,
        "source_document_id": job.source_document_id,
        "title": job.title,
        "company_name": job.company_name,
        "job_url": job.job_url,
        "target_direction": job.target_direction,
        "created_at": job.created_at,
    }


@router.post("")
def create_job_description(
    payload: JobDescriptionCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    job = JobService().create_job_description(
        db,
        user_id=get_settings().default_user_id,
        source_document_id=payload.source_document_id,
        title=payload.title,
        company_name=payload.company_name,
        job_url=payload.job_url,
        target_direction=payload.target_direction,
    )
    return success_response(serialize_job(job), request.state.request_id)


@router.post("/{job_description_id}/parse")
async def parse_job_description(
    job_description_id: UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    profile, agent_run_id = await JobService().parse_job_description(
        db, job_description_id=job_description_id
    )
    return success_response(
        {
            "job_description_id": profile.job_description_id,
            "jd_profile_id": profile.id,
            "agent_run_id": agent_run_id,
        },
        request.state.request_id,
    )
