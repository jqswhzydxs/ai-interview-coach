import pytest
import httpx

from app.agents.base import BaseAgent
from app.agents.deepseek_client import DeepSeekClient
from app.agents.kimi_client import KimiClient
from app.agents.llm_client import LLMRequest, get_llm_client
from app.agents.mock_client import MockLLMClient
from app.core.config import get_settings


@pytest.mark.asyncio
async def test_mock_provider_returns_fixed_json(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("LLM_MODEL", "mock-model")
    get_settings.cache_clear()

    client = get_llm_client()
    response = await client.generate_json(
        LLMRequest(system_prompt="system", user_prompt="user", response_schema_name="TestSchema")
    )

    assert isinstance(client, MockLLMClient)
    assert response.provider == "mock"
    assert response.model_name == "mock-model"
    assert response.content["status"] == "ok"
    assert response.content["schema"] == "TestSchema"


def test_invalid_provider_returns_clear_error(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "unknown")
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        get_llm_client()


def test_deepseek_and_kimi_provider_skeletons(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    get_settings.cache_clear()
    assert isinstance(get_llm_client(), DeepSeekClient)

    monkeypatch.setenv("LLM_PROVIDER", "kimi")
    monkeypatch.setenv("KIMI_API_KEY", "test-key")
    get_settings.cache_clear()
    assert isinstance(get_llm_client(), KimiClient)


@pytest.mark.asyncio
async def test_deepseek_provider_posts_openai_compatible_json() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"score": 88}'}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = DeepSeekClient(
            api_key="test-key",
            model_name="deepseek-chat",
            http_client=http_client,
        )
        response = await client.generate_json(
            LLMRequest(system_prompt="system", user_prompt="user", temperature=0.1)
        )

    assert requests[0].url == "https://api.deepseek.com/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer test-key"
    assert response.provider == "deepseek"
    assert response.content == {"score": 88}


@pytest.mark.asyncio
async def test_kimi_provider_posts_openai_compatible_json() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"score": 92}'}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = KimiClient(
            api_key="test-key",
            model_name="kimi-latest",
            http_client=http_client,
        )
        response = await client.generate_json(
            LLMRequest(system_prompt="system", user_prompt="user", temperature=0.1)
        )

    assert requests[0].url == "https://api.moonshot.cn/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer test-key"
    assert response.provider == "kimi"
    assert response.content == {"score": 92}


def test_base_agent_uses_llm_client_abstraction() -> None:
    class EchoAgent(BaseAgent):
        name = "echo_agent"
        prompt_version = "echo_agent_v0.1"

    agent = EchoAgent(llm_client=MockLLMClient(model_name="mock-model"))

    assert isinstance(agent.llm_client, MockLLMClient)
    assert agent.name == "echo_agent"
    assert agent.prompt_version == "echo_agent_v0.1"
