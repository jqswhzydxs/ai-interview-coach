from collections.abc import Callable
from typing import Any

import pytest
from pydantic import BaseModel

from app.agents.answer_evaluator import AnswerEvaluatorAgent
from app.agents.experience_analyzer import ExperienceAnalyzerAgent
from app.agents.jd_analyzer import JDAnalyzerAgent
from app.agents.llm_client import LLMJSONError, LLMRequest, LLMResponse, TokenUsage
from app.agents.matching_agent import MatchingAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.mock_client import MockLLMClient
from app.agents.resume_analyzer import ResumeAnalyzerAgent
from app.schemas.evaluation import AnswerEvaluation
from app.schemas.experience import ExperienceProfile
from app.schemas.job_description import JDProfile
from app.schemas.memory import MemoryUpdate
from app.schemas.prep_package import MatchReport
from app.schemas.resume import ResumeProfile


class FakeRealProviderClient:
    provider = "deepseek"
    model_name = "fake-real-model"

    def __init__(self, content: dict | None = None, exc: Exception | None = None) -> None:
        self.content = content
        self.exc = exc
        self.calls = 0

    async def generate_json(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        if self.exc is not None:
            raise self.exc
        return LLMResponse(
            provider=self.provider,
            model_name=self.model_name,
            content=self.content or {},
            usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            raw_text=None,
        )


AgentFactory = Callable[[Any], Any]


@pytest.fixture(
    params=[
        (
            ResumeAnalyzerAgent,
            ResumeProfile,
            {"raw_text": "Python FastAPI PostgreSQL project"},
        ),
        (
            JDAnalyzerAgent,
            JDProfile,
            {"raw_text": "Python FastAPI backend engineer", "title": "Backend Engineer"},
        ),
        (
            ExperienceAnalyzerAgent,
            ExperienceProfile,
            {"raw_text": "FastAPI database transaction interview notes"},
        ),
        (
            MatchingAgent,
            MatchReport,
            {"resume_profile": {"skills": ["Python"]}, "jd_profile": {"tech_keywords": ["Python"]}},
        ),
        (
            AnswerEvaluatorAgent,
            AnswerEvaluation,
            {"question_text": "Explain your FastAPI project.", "user_answer": "I built APIs."},
        ),
        (MemoryAgent, MemoryUpdate, {"answer_evaluation": {"total_score": 76}}),
    ],
    ids=["resume", "jd", "experience", "matching", "evaluation", "memory"],
)
def agent_case(request) -> tuple[AgentFactory, type[BaseModel], dict]:
    return request.param


async def _rule_based_output(agent_factory: AgentFactory, input_data: dict) -> dict:
    return await agent_factory(MockLLMClient()).run(input_data)


@pytest.mark.asyncio
async def test_real_llm_agent_accepts_schema_valid_output(agent_case) -> None:
    agent_factory, output_schema, input_data = agent_case
    valid_content = await _rule_based_output(agent_factory, input_data)
    client = FakeRealProviderClient(content=valid_content)
    agent = agent_factory(client)

    output = await agent.run(input_data)

    assert client.calls == 1
    assert output_schema.model_validate(output).model_dump(mode="json") == output
    assert agent.last_execution is not None
    assert agent.last_execution.execution_mode == "real"
    assert agent.last_execution.real_call_count == 1
    assert agent.last_execution.retry_count == 0
    assert agent.last_execution.total_tokens == 15


@pytest.mark.asyncio
async def test_real_llm_agent_falls_back_after_invalid_json(agent_case) -> None:
    agent_factory, output_schema, input_data = agent_case
    client = FakeRealProviderClient(
        exc=LLMJSONError(
            "Invalid JSON",
            usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
        )
    )

    agent = agent_factory(client)
    output = await agent.run(input_data)

    assert client.calls == 2
    output_schema.model_validate(output)
    assert agent.last_execution is not None
    assert agent.last_execution.execution_mode == "fallback"
    assert agent.last_execution.real_call_count == 2
    assert agent.last_execution.retry_count == 1
    assert agent.last_execution.failure_counts == {"json": 2}
    assert agent.last_execution.fallback_reason == {
        "code": "invalid_json",
        "failure_type": "json",
        "stage": "response_parse",
        "attempt": 2,
    }
    assert agent.last_execution.total_tokens == 30


@pytest.mark.asyncio
async def test_real_llm_agent_falls_back_after_schema_mismatch(agent_case) -> None:
    agent_factory, output_schema, input_data = agent_case
    client = FakeRealProviderClient(content={"unexpected": "response"})

    agent = agent_factory(client)
    output = await agent.run(input_data)

    assert client.calls == 2
    output_schema.model_validate(output)
    assert agent.last_execution is not None
    assert agent.last_execution.failure_counts == {"schema": 2}


@pytest.mark.asyncio
async def test_real_llm_agent_falls_back_after_provider_timeout(agent_case) -> None:
    agent_factory, output_schema, input_data = agent_case
    client = FakeRealProviderClient(exc=TimeoutError("provider timed out"))

    agent = agent_factory(client)
    output = await agent.run(input_data)

    assert client.calls == 2
    output_schema.model_validate(output)
    assert agent.last_execution is not None
    assert agent.last_execution.failure_counts == {"timeout": 2}
