from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.response import success_response
from app.services.agent_run_service import AgentRunService


router = APIRouter(prefix="/agent-runs")


@router.get("/{agent_run_id}")
def get_agent_run(
    agent_run_id: UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    data = AgentRunService().get_run_detail(db, agent_run_id)
    return success_response(data, request.state.request_id)
