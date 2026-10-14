from fastapi import APIRouter, Request

from app.core.config import get_settings
from app.schemas.response import success_response


router = APIRouter()


@router.get("/health")
def health_check(request: Request) -> dict:
    settings = get_settings()
    return success_response(
        data={
            "status": "ok",
            "app_name": settings.app_name,
            "environment": settings.app_env,
        },
        request_id=request.state.request_id,
    )
