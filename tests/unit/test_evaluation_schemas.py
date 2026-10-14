from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.agent import AgentRunResponse, AgentRunStepResponse
from app.schemas.evaluation import AnswerEvaluation


def metadata() -> dict:
    return {
        "schema_version": "v0.1",
        "generated_at": datetime.now(timezone.utc),
        "agent_name": "answer_evaluator",
        "prompt_version": "answer_evaluator_v0.1",
    }


def valid_evaluation_payload() -> dict:
    return {
        **metadata(),
        "question_id": "pro-1",
        "question_text": "Explain your FastAPI project.",
        "user_answer": "I designed the API and database schema.",
        "total_score": 78,
        "dimension_scores": [
            {"name": "relevance", "score": 18, "max_score": 20, "reason": "mostly relevant"},
            {"name": "technical_accuracy", "score": 20, "max_score": 25, "reason": "accurate"},
        ],
        "overall_comment": "Good structure, needs metrics.",
        "strengths": ["Clear ownership"],
        "improvement_points": ["Add measurable impact"],
        "risks": ["May sound generic"],
        "improved_answer": "In my FastAPI project, I owned API design and measured latency.",
        "follow_up_questions": ["What tradeoff did you make?"],
        "next_practice_suggestion": "Practice project metrics.",
        "memory_update": {"confidence": 0.8, "content": "Needs metrics"},
    }


def test_answer_evaluation_accepts_valid_payload() -> None:
    evaluation = AnswerEvaluation(**valid_evaluation_payload())

    assert evaluation.total_score == 78
    assert evaluation.dimension_scores[0].score <= evaluation.dimension_scores[0].max_score


def test_answer_evaluation_rejects_total_score_above_100() -> None:
    payload = valid_evaluation_payload()
    payload["total_score"] = 101

    with pytest.raises(ValidationError):
        AnswerEvaluation(**payload)


def test_answer_evaluation_rejects_dimension_score_above_max() -> None:
    payload = valid_evaluation_payload()
    payload["dimension_scores"][0]["score"] = 21
    payload["dimension_scores"][0]["max_score"] = 20

    with pytest.raises(ValidationError):
        AnswerEvaluation(**payload)


def test_answer_evaluation_requires_improvement_and_follow_up() -> None:
    payload = valid_evaluation_payload()
    payload["improvement_points"] = []
    payload["follow_up_questions"] = []

    with pytest.raises(ValidationError):
        AnswerEvaluation(**payload)


def test_agent_run_response_orders_steps() -> None:
    now = datetime.now(timezone.utc)
    response = AgentRunResponse(
        id="00000000-0000-0000-0000-000000000001",
        run_type="answer_evaluation",
        status="succeeded",
        prompt_version="answer_evaluator_v0.1",
        steps=[
            AgentRunStepResponse(
                id="00000000-0000-0000-0000-000000000003",
                step_order=2,
                agent_name="memory_agent",
                action_type="suggest_memory",
                status="succeeded",
                error_message=None,
                latency_ms=10,
                created_at=now,
            ),
            AgentRunStepResponse(
                id="00000000-0000-0000-0000-000000000002",
                step_order=1,
                agent_name="answer_evaluator",
                action_type="evaluate",
                status="succeeded",
                error_message=None,
                latency_ms=20,
                created_at=now,
            ),
        ],
        error_message=None,
        created_at=now,
    )

    assert [step.step_order for step in response.steps] == [1, 2]
