from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.deps import get_db
from app.services.prep_package_service import PrepPackageService
from app.services.question_service import QuestionService
from app.schemas.response import success_response


router = APIRouter(prefix="/prep-packages")


class PrepPackageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resume_id: UUID
    job_description_id: UUID
    interview_experience_ids: list[UUID] = Field(default_factory=list)
    preparation_goal: str = Field(min_length=1)
    title: str | None = None


@router.post("")
async def create_prep_package(
    payload: PrepPackageCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    package, agent_run_id = await PrepPackageService().create_prep_package(
        db,
        user_id=get_settings().default_user_id,
        resume_id=payload.resume_id,
        job_description_id=payload.job_description_id,
        interview_experience_ids=payload.interview_experience_ids,
        preparation_goal=payload.preparation_goal,
        title=payload.title,
    )
    return success_response(
        {
            "prep_package_id": package.id,
            "agent_run_id": agent_run_id,
            "status": package.status,
        },
        request.state.request_id,
    )


@router.get("/{prep_package_id}")
def get_prep_package(
    prep_package_id: UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    data = QuestionService().get_prep_package_detail(db, prep_package_id)
    return success_response(data, request.state.request_id)


@router.get("/{prep_package_id}/questions")
def list_questions(
    prep_package_id: UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    module: str | None = None,
    difficulty: str | None = None,
) -> dict:
    data = QuestionService().list_questions(
        db,
        prep_package_id=prep_package_id,
        module=module,
        difficulty=difficulty,
    )
    return success_response(data, request.state.request_id)
