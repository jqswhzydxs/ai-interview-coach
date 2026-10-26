"""Experiment-only DeepSeek client with explicit thinking-mode injection.

The production ``DeepSeekClient`` remains unchanged.  This client is created
only by the Phase 2.4D-D-A readiness and A/B CLIs and requires an explicit
``thinking_type`` dependency at construction time.
"""

from __future__ import annotations

import json
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.agents.deepseek_client import DeepSeekClient
from app.agents.llm_client import (
    LLMJSONError,
    LLMRequest,
    LLMResponseError,
    TokenUsage,
)
from app.services.provider_usage_details import parse_provider_usage_details


ThinkingType = Literal["enabled", "disabled"]
USAGE_DETAIL_FIELDS = (
    "reasoning_tokens",
    "visible_completion_tokens",
    "cached_input_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


class WhitelistedUsageDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning_tokens: int | None = Field(default=None, ge=0)
    visible_completion_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    cache_read_input_tokens: int | None = Field(default=None, ge=0)
    cache_creation_input_tokens: int | None = Field(default=None, ge=0)


class DeepSeekThinkingExperimentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model_name: str
    content: dict
    usage: TokenUsage | None = None
    raw_text: str | None = Field(default=None, exclude=True, repr=False)
    usage_details: WhitelistedUsageDetails | None = Field(
        default=None,
        exclude=True,
        repr=False,
    )


def safe_usage_details_record(response: object) -> dict[str, dict[str, int | str | None]]:
    """Return explicit numeric details or ``unknown`` without deriving values."""

    details = getattr(response, "usage_details", None)
    return {
        field: {
            "status": (
                "available"
                if details is not None and getattr(details, field, None) is not None
                else "unknown"
            ),
            "value": getattr(details, field, None) if details is not None else None,
        }
        for field in USAGE_DETAIL_FIELDS
    }


class DeepSeekThinkingExperimentClient(DeepSeekClient):
    """DeepSeek chat client whose sole request delta is ``thinking.type``."""

    def __init__(
        self,
        api_key: str,
        model_name: str,
        *,
        thinking_type: ThinkingType,
        base_url: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if thinking_type not in {"enabled", "disabled"}:
            raise ValueError("thinking_type must be explicitly enabled or disabled")
        self.thinking_type: ThinkingType = thinking_type
        super().__init__(
            api_key=api_key,
            model_name=model_name,
            base_url=base_url,
            http_client=http_client,
        )

    def request_payload(self, request: LLMRequest) -> dict:
        """Build the exact experiment request body for inspection and transport."""

        return {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": request.temperature,
            "response_format": {"type": "json_object"},
            "thinking": {"type": self.thinking_type},
        }

    async def generate_json(self, request: LLMRequest) -> DeepSeekThinkingExperimentResponse:
        payload = self.request_payload(request)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.http_client is not None:
            response = await self.http_client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=60,
            )
        else:
            async with httpx.AsyncClient(timeout=60) as http_client:
                response = await http_client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
        response.raise_for_status()
        try:
            response_json = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise LLMJSONError("Provider returned an invalid JSON response envelope") from exc

        usage = self._extract_usage(response_json)
        usage_details = self._extract_usage_details(response_json)
        try:
            raw_text = response_json["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError(
                "Provider response is missing the assistant message",
                usage=usage,
            ) from exc
        try:
            content = self._parse_json_content(raw_text)
        except LLMJSONError as exc:
            exc.usage = usage
            raise
        return DeepSeekThinkingExperimentResponse(
            provider=self.provider,
            model_name=self.model_name,
            content=content,
            usage=usage,
            usage_details=usage_details,
            raw_text=raw_text,
        )

    @staticmethod
    def _extract_usage_details(response_json: dict) -> WhitelistedUsageDetails | None:
        parsed = parse_provider_usage_details(response_json)
        values = {
            field: parsed["fields"][field]["value"]
            if parsed["fields"][field]["status"] == "available"
            else None
            for field in USAGE_DETAIL_FIELDS
        }
        if not any(value is not None for value in values.values()):
            return None
        return WhitelistedUsageDetails(**values)
