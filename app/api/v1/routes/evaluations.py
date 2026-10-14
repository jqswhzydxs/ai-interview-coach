from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.deps import get_db
from app.schemas.pagination import PaginationParams
from app.schemas.response import success_response
from app.services.evaluation_service import EvaluationService


router = APIRouter(prefix="/evaluations")


class EvaluationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_db_id: UUID | None = None
    custom_question_text: str | None = None
    user_answer: str = Field(min_length=1)


@router.post("")
async def create_evaluation(
    payload: EvaluationCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    service = EvaluationService()
    evaluation, agent_run_id = await service.create_evaluation(
        db,
        user_id=get_settings().default_user_id,
        question_db_id=payload.question_db_id,
        custom_question_text=payload.custom_question_text,
        user_answer=payload.user_answer,
    )
    return success_response(
        {
            "answer_evaluation_id": evaluation.id,
            "agent_run_id": agent_run_id,
            "total_score": float(evaluation.total_score),
        },
        request.state.request_id,
    )


@router.get("")
def list_evaluations(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    pagination: Annotated[PaginationParams, Depends()],
) -> dict:
    data = EvaluationService().list_evaluations(
        db, limit=pagination.limit, offset=pagination.offset
    )
    return success_response(data, request.state.request_id)


@router.get("/{answer_evaluation_id}")
def get_evaluation(
    answer_evaluation_id: UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    service = EvaluationService()
    evaluation = service.get_evaluation(db, answer_evaluation_id)
    return success_response(service.serialize_detail(evaluation), request.state.request_id)
