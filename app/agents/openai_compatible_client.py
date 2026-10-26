import json
import re

import httpx

from app.agents.llm_client import (
    LLMJSONError,
    LLMRequest,
    LLMResponse,
    LLMResponseError,
    TokenUsage,
)


class OpenAICompatibleChatClient:
    provider: str

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        base_url: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client

    async def generate_json(self, request: LLMRequest) -> LLMResponse:
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": request.temperature,
            "response_format": {"type": "json_object"},
        }
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
        return LLMResponse(
            provider=self.provider,
            model_name=self.model_name,
            content=content,
            usage=usage,
            raw_text=raw_text,
        )

    def _parse_json_content(self, raw_text: str | dict) -> dict:
        if isinstance(raw_text, dict):
            return raw_text
        stripped = raw_text.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
        if fenced is not None:
            stripped = fenced.group(1).strip()
        try:
            parsed = json.loads(stripped)
        except (json.JSONDecodeError, TypeError) as exc:
            raise LLMJSONError("Model content is not a valid JSON object") from exc
        if not isinstance(parsed, dict):
            raise LLMJSONError("Model content is not a JSON object")
        return parsed

    def _extract_usage(self, response_json: dict) -> TokenUsage | None:
        raw_usage = response_json.get("usage")
        if not isinstance(raw_usage, dict):
            return None

        input_tokens = self._non_negative_int(
            raw_usage.get("prompt_tokens", raw_usage.get("input_tokens"))
        )
        output_tokens = self._non_negative_int(
            raw_usage.get("completion_tokens", raw_usage.get("output_tokens"))
        )
        total_tokens = self._non_negative_int(raw_usage.get("total_tokens"))
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens
        if input_tokens is None and output_tokens is None and total_tokens is None:
            return None
        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

    @staticmethod
    def _non_negative_int(value: object) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int) and value >= 0:
            return value
        return None
