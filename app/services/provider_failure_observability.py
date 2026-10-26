"""Fail-closed, report-only diagnostics. Never serialize an exception or response."""

import asyncio
from datetime import timezone
from email.utils import format_datetime, parsedate_to_datetime
import re
import socket
from uuid import UUID

import httpx

from app.agents.llm_client import LLMJSONError, LLMResponseError, TokenUsage


TOKEN_FIELDS = ("input_tokens", "output_tokens", "total_tokens")
# Unknown codes are omitted, even if they look like harmless identifiers.
PROVIDER_CODES = frozenset({
    "invalid_api_key", "authentication_error", "authentication_failed",
    "permission_denied", "model_access_denied", "model_permission_denied",
    "model_not_found", "rate_limit_exceeded", "rate_limit_error",
    "insufficient_quota", "invalid_request", "invalid_request_error",
    "invalid_parameter", "context_length_exceeded", "server_error",
    "internal_server_error", "service_unavailable", "overloaded_error",
})
EXCEPTION_TYPES = (
    httpx.HTTPStatusError, httpx.ConnectTimeout, httpx.ReadTimeout,
    httpx.WriteTimeout, httpx.PoolTimeout, httpx.ConnectError, httpx.ReadError,
    httpx.WriteError, httpx.CloseError, httpx.RemoteProtocolError,
    httpx.LocalProtocolError, httpx.ProxyError, httpx.UnsupportedProtocol,
    httpx.NetworkError, httpx.ProtocolError, httpx.TimeoutException,
    httpx.RequestError, LLMJSONError, LLMResponseError,
    asyncio.CancelledError, TimeoutError, ConnectionError, socket.gaierror,
)


def safe_token_usage(usage: object) -> dict:
    return {
        key: value if type(value) is int and value >= 0 else None
        for key in TOKEN_FIELDS
        for value in [getattr(usage, key, None) if isinstance(usage, TokenUsage) else None]
    }


def usage_status(usage: dict) -> str:
    present = sum(usage.get(key) is not None for key in TOKEN_FIELDS)
    return "available" if present == 3 else "not_available" if present == 0 else "unknown"


def _sensitive(value: str, sensitive_values: tuple[str, ...]) -> bool:
    if re.search(r"authorization|bearer|api[_-]?key|secret|prompt|raw[_-]?response|sk-", value, re.I):
        return True
    return any(secret and (secret in value or value in secret) for secret in sensitive_values)


def _request_id(value: object, sensitive_values: tuple[str, ...]) -> str | None:
    if not isinstance(value, str) or not 8 <= len(value) <= 96:
        return None
    if _sensitive(value, sensitive_values):
        return None
    try:
        if str(UUID(value)) == value.lower():
            return value
    except ValueError:
        pass
    if re.fullmatch(r"[0-9a-fA-F]{16,64}|req[-_][A-Za-z0-9_-]{8,80}", value):
        return value
    return None


def _retry_after(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 40:
        return None
    if re.fullmatch(r"[0-9]{1,6}", value) and int(value) <= 604800:
        return str(int(value))
    if not re.fullmatch(r"[A-Z][a-z]{2}, \d{2} [A-Z][a-z]{2} \d{4} \d{2}:\d{2}:\d{2} GMT", value):
        return None
    try:
        parsed = parsedate_to_datetime(value)
        return format_datetime(parsed.astimezone(timezone.utc), usegmt=True)
    except (ValueError, TypeError, OverflowError):
        return None


def provider_failure_fields(
    exc: BaseException, *, sensitive_values: tuple[str, ...] = (),
) -> dict:
    """Extract only typed, bounded values; never call str/repr on exceptions."""
    exception_type = next(
        (kind.__name__ for kind in EXCEPTION_TYPES if isinstance(exc, kind)),
        "OtherProviderError",
    )
    status = None
    code = None
    request_id = None
    retry_after = None
    filtered = []
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        raw_status = response.status_code
        status = raw_status if type(raw_status) is int and 100 <= raw_status <= 599 else None
        try:
            authorization = exc.request.headers.get("authorization", "")
        except (RuntimeError, AttributeError):
            authorization = ""
        auth_parts = authorization.split(None, 1)
        protected = sensitive_values + tuple(
            part for part in (authorization, auth_parts[1] if len(auth_parts) == 2 else "") if part
        )
        # Only the nested scalar error.code is eligible. No message/body is retained.
        try:
            envelope = response.json()
            error = envelope.get("error") if isinstance(envelope, dict) else None
            raw_code = error.get("code") if isinstance(error, dict) else None
        except (ValueError, TypeError, UnicodeError, httpx.ResponseNotRead):
            raw_code = None
        if (
            isinstance(raw_code, str) and raw_code in PROVIDER_CODES
            and not any(secret and (secret in raw_code or raw_code in secret) for secret in protected)
        ):
            code = raw_code
        elif raw_code is not None:
            filtered.append("provider_error_code")
        # Never copy the headers object. Authorization is used only for rejection.
        raw_id = response.headers.get("x-request-id", response.headers.get("request-id"))
        request_id = _request_id(raw_id, protected)
        if raw_id is not None and request_id is None:
            filtered.append("request_id")
        raw_retry = response.headers.get("retry-after")
        retry_after = _retry_after(raw_retry)
        if raw_retry is not None and (retry_after is None or _sensitive(retry_after, protected)):
            retry_after = None
            filtered.append("retry_after")

    if status == 401:
        category = "auth"
    elif status == 403:
        category = "permission"
    elif status == 429:
        category = "rate_limit"
    elif status is not None and 500 <= status <= 599:
        category = "provider_server"
    elif code in {"permission_denied", "model_access_denied", "model_permission_denied"}:
        category = "permission"
    elif status is not None and 400 <= status <= 499:
        category = "invalid_request"
    elif isinstance(exc, httpx.ConnectTimeout):
        category = "connect_timeout"
    elif isinstance(exc, httpx.ReadTimeout):
        category = "read_timeout"
    elif (
        isinstance(exc, (ConnectionError, socket.gaierror))
        or isinstance(exc, httpx.RequestError) and not isinstance(exc, httpx.TimeoutException)
    ):
        category = "network"
    else:
        category = "unknown_provider"
    return {
        "failure_category": category,
        "exception_type": exception_type,
        "http_status_code": status,
        "provider_error_code": code,
        "request_id": request_id,
        "retry_after": retry_after,
        "filtered_fields": filtered,
    }
