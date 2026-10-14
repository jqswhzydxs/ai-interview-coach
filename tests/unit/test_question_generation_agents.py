import pytest
from pydantic import ValidationError

from app.agents.matching_agent import MatchingAgent
from app.agents.mock_client import MockLLMClient
from app.agents.question_bank_agent import QuestionBankAgent
from app.schemas.prep_package import MatchReport
from app.schemas.question import QuestionBank


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
