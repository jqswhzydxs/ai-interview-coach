import json
import re

import httpx

from app.agents.llm_client import LLMRequest, LLMResponse


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
        response_json = response.json()
        raw_text = response_json["choices"][0]["message"]["content"]
        content = self._parse_json_content(raw_text)
        return LLMResponse(
            provider=self.provider,
            model_name=self.model_name,
            content=content,
            raw_text=raw_text,
        )

    def _parse_json_content(self, raw_text: str | dict) -> dict:
        if isinstance(raw_text, dict):
            return raw_text
        stripped = raw_text.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
        if fenced is not None:
            stripped = fenced.group(1).strip()
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            raise ValueError("LLM response must be a JSON object")
        return parsed
