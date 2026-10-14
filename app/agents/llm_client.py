from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings, get_settings


class LLMRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system_prompt: str
    user_prompt: str
    response_schema_name: str | None = None
    temperature: float = Field(default=0.2, ge=0, le=2)


class LLMResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model_name: str
    content: dict
    raw_text: str | None = None


class LLMClient(Protocol):
    provider: str
    model_name: str

    async def generate_json(self, request: LLMRequest) -> LLMResponse:
        ...


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    resolved_settings = settings or get_settings()
    provider = resolved_settings.llm_provider.lower()

    if provider == "mock":
        from app.agents.mock_client import MockLLMClient

        return MockLLMClient(model_name=resolved_settings.llm_model or "mock")
    if provider == "deepseek":
        from app.agents.deepseek_client import DeepSeekClient

        return DeepSeekClient(
            api_key=resolved_settings.deepseek_api_key,
            model_name=resolved_settings.llm_model or "deepseek-chat",
        )
    if provider == "kimi":
        from app.agents.kimi_client import KimiClient

        return KimiClient(
            api_key=resolved_settings.kimi_api_key,
            model_name=resolved_settings.llm_model or "kimi-latest",
        )

    raise ValueError(f"Unsupported LLM provider: {resolved_settings.llm_provider}")
