import pytest
from pydantic import ValidationError

from app.schemas.pagination import PaginationParams
from app.schemas.response import ErrorPayload, ErrorResponse, SuccessResponse


def test_success_response_schema() -> None:
    response = SuccessResponse(data={"status": "ok"}, request_id="req-1")

    assert response.message == "ok"
    assert response.request_id == "req-1"
    assert response.data == {"status": "ok"}


def test_error_response_schema() -> None:
    response = ErrorResponse(
        error=ErrorPayload(code="NOT_FOUND", message="Not found", details={})
    )

    assert response.error.code == "NOT_FOUND"
    assert response.error.details == {}


def test_pagination_defaults_and_bounds() -> None:
    params = PaginationParams()

    assert params.limit == 20
    assert params.offset == 0

    with pytest.raises(ValidationError):
        PaginationParams(limit=101)

    with pytest.raises(ValidationError):
        PaginationParams(offset=-1)

