import pytest
from pydantic import ValidationError

from app.agents.llm_client import LLMRequest, LLMResponse
from app.agents.matching_agent import MatchingAgent
from app.agents.mock_client import MockLLMClient
from app.agents.question_bank_agent import QuestionBankAgent
from app.schemas.prep_package import MatchReport
from app.schemas.question import QuestionBank


class FakeProviderClient:
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
            raw_text=None,
        )


@pytest.mark.asyncio
async def test_matching_agent_mock_outputs_valid_match_report() -> None:
    agent = MatchingAgent(llm_client=MockLLMClient())

    output = await agent.run(
        {
            "resume_profile": {"skills": ["Python", "FastAPI"]},
            "jd_profile": {"tech_keywords": ["Python", "PostgreSQL"]},
            "preparation_goal": "prepare backend interview",
        }
    )
    report = MatchReport.model_validate(output)

    assert report.overall_score >= 0
    assert report.evidence_refs[0].source_type == "resume"


@pytest.mark.asyncio
async def test_question_bank_agent_mock_outputs_valid_question_bank() -> None:
    agent = QuestionBankAgent(llm_client=MockLLMClient())

    output = await agent.run({"match_report": {"summary": "Good backend fit"}})
    bank = QuestionBank.model_validate(output)

    assert bank.total_count == 25
    assert len(bank.self_intro_questions) >= 8
    assert len(bank.professional_questions) >= 8
    assert len(bank.behavior_project_questions) >= 8
    assert all(question.source_refs for question in bank.self_intro_questions)
    assert all(question.scoring_anchors for question in bank.professional_questions)


@pytest.mark.asyncio
async def test_question_bank_agent_24_question_output_fails_schema_validation() -> None:
    agent = QuestionBankAgent(llm_client=MockLLMClient(), total_count=24)

    output = await agent.run({"match_report": {"summary": "Too few questions"}})

    with pytest.raises(ValidationError):
        QuestionBank.model_validate(output)


@pytest.mark.asyncio
async def test_question_bank_agent_real_llm_success_uses_valid_provider_output() -> None:
    valid_content = QuestionBankAgent(llm_client=MockLLMClient())._rule_based_question_bank()
    valid_content["self_intro_questions"][0]["question_text"] = "LLM generated question"
    client = FakeProviderClient(content=valid_content)
    agent = QuestionBankAgent(llm_client=client)

    output = await agent.run({"match_report": {"summary": "Use real provider"}})
    bank = QuestionBank.model_validate(output)

    assert client.calls == 1
    assert bank.self_intro_questions[0].question_text == "LLM generated question"


@pytest.mark.asyncio
async def test_question_bank_agent_falls_back_when_provider_json_is_invalid() -> None:
    client = FakeProviderClient(exc=ValueError("Invalid JSON"))
    agent = QuestionBankAgent(llm_client=client)

    output = await agent.run({"match_report": {"summary": "Bad JSON"}})
    bank = QuestionBank.model_validate(output)

    assert client.calls == 2
    assert bank.total_count == 25
    assert bank.self_intro_questions[0].question_text != "LLM generated question"


@pytest.mark.asyncio
async def test_question_bank_agent_falls_back_when_provider_schema_mismatches() -> None:
    client = FakeProviderClient(content={"total_count": 1})
    agent = QuestionBankAgent(llm_client=client)

    output = await agent.run({"match_report": {"summary": "Bad schema"}})
    bank = QuestionBank.model_validate(output)

    assert client.calls == 2
    assert bank.total_count == 25
    assert len(bank.professional_questions) >= 8


@pytest.mark.asyncio
async def test_question_bank_agent_falls_back_when_provider_times_out() -> None:
    client = FakeProviderClient(exc=TimeoutError("provider timed out"))
    agent = QuestionBankAgent(llm_client=client)

    output = await agent.run({"match_report": {"summary": "Timeout"}})
    bank = QuestionBank.model_validate(output)

    assert client.calls == 2
    assert bank.total_count == 25
    assert len(bank.behavior_project_questions) >= 8
