from app.agents.llm_client import LLMRequest, LLMResponse


class MockLLMClient:
    provider = "mock"

    def __init__(self, model_name: str = "mock") -> None:
        self.model_name = model_name

    async def generate_json(self, request: LLMRequest) -> LLMResponse:
        content = {
            "status": "ok",
            "schema": request.response_schema_name,
            "message": "mock llm response",
        }
        return LLMResponse(
            provider=self.provider,
            model_name=self.model_name,
            content=content,
            raw_text=None,
        )
