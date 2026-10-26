import os

import pytest

from app.agents.llm_client import LLMRequest, get_llm_client
from app.core.config import get_settings


pytestmark = [
    pytest.mark.real_llm,
    pytest.mark.skipif(
        os.getenv("RUN_REAL_LLM_SMOKE_TESTS") != "1",
        reason="real LLM smoke tests are disabled by default",
    ),
]


@pytest.mark.asyncio
async def test_configured_real_llm_provider_returns_json() -> None:
    provider = os.getenv("LLM_PROVIDER", "mock").lower()
    if provider == "mock":
        pytest.skip("LLM_PROVIDER must be deepseek or kimi for real smoke tests")
    if provider == "deepseek" and not os.getenv("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY is required for DeepSeek smoke tests")
    if provider == "kimi" and not os.getenv("KIMI_API_KEY"):
        pytest.skip("KIMI_API_KEY is required for Kimi smoke tests")

    get_settings.cache_clear()
    client = get_llm_client()
    response = await client.generate_json(
        LLMRequest(
            system_prompt="Return only one JSON object.",
            user_prompt='Return {"status":"ok"} with no extra text.',
            response_schema_name="ProviderSmoke",
            temperature=0,
        )
    )

    assert response.provider == provider
    assert isinstance(response.content, dict)
    assert response.content
