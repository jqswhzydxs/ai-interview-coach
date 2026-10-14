import pytest

from app.agents.answer_evaluator import AnswerEvaluatorAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.mock_client import MockLLMClient
from app.schemas.evaluation import AnswerEvaluation
from app.schemas.memory import MemoryItem


@pytest.mark.asyncio
async def test_answer_evaluator_mock_outputs_valid_evaluation() -> None:
    agent = AnswerEvaluatorAgent(llm_client=MockLLMClient())

    output = await agent.run(
        {
            "question_text": "Explain your FastAPI project.",
            "user_answer": "I built APIs with FastAPI and PostgreSQL.",
        }
    )
    evaluation = AnswerEvaluation.model_validate(output)

    assert 0 <= evaluation.total_score <= 100
    assert all(item.score <= item.max_score for item in evaluation.dimension_scores)
    assert evaluation.improvement_points
    assert evaluation.follow_up_questions


@pytest.mark.asyncio
async def test_memory_agent_mock_outputs_valid_memory_suggestion() -> None:
    agent = MemoryAgent(llm_client=MockLLMClient())

    output = await agent.run({"answer_evaluation": {"total_score": 76}})
    items = [MemoryItem.model_validate(item) for item in output["memory_items"]]

    assert len(items) >= 1
    assert items[0].source_type == "answer_evaluation"
    assert items[0].confidence >= 0.8
