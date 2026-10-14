from typing import Any

from pydantic import BaseModel, Field


class SuccessResponse(BaseModel):
    data: Any
    message: str = "ok"
    request_id: str


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorPayload


def success_response(data: Any, request_id: str, message: str = "ok") -> dict[str, Any]:
    return SuccessResponse(data=data, message=message, request_id=request_id).model_dump()

