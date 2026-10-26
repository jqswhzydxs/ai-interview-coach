import json
from pathlib import Path
import re

import pytest
from pydantic import ValidationError

from app.agents.answer_evaluator import AnswerEvaluatorAgent
from app.agents.llm_client import LLMRequest
from app.agents.memory_agent import MemoryAgent
from app.agents.mock_client import MockLLMClient
from app.agents.question_bank_agent import QuestionBankAgent
from app.agents.resume_analyzer import ResumeAnalyzerAgent
from app.agents.source_quality import aggregate_source_quality, fallback_source_names
from app.core.config import get_settings
from app.schemas.evaluation import AnswerEvaluation
from app.schemas.memory import MemoryUpdate
from app.schemas.question import QuestionBank


class NeverCalledProvider:
    provider = "deepseek"
    model_name = "fake-model"

    def __init__(self) -> None:
        self.calls = 0

    async def generate_json(self, request: LLMRequest):
        self.calls += 1
        raise AssertionError("policy fallback must not call provider")


class TimeoutProvider(NeverCalledProvider):
    async def generate_json(self, request: LLMRequest):
        self.calls += 1
        raise TimeoutError("synthetic timeout")


def test_test_environment_ignores_dotenv_and_uses_safe_defaults(
    tmp_path, monkeypatch
) -> None:
    (tmp_path / ".env").write_text(
        "LLM_PROVIDER=deepseek\n"
        "DEEPSEEK_API_KEY=must-not-load\n"
        "RUN_REAL_LLM_ACCEPTANCE=true\n"
        "SAVE_FULL_LLM_LOGS=true\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("RUN_REAL_LLM_ACCEPTANCE", raising=False)
    monkeypatch.delenv("SAVE_FULL_LLM_LOGS", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.llm_provider == "mock"
    assert settings.deepseek_api_key == ""
    assert settings.run_real_llm_acceptance is False
    assert settings.save_full_llm_logs is False
    get_settings.cache_clear()


def test_test_environment_accepts_explicit_process_config_without_dotenv(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-explicit-key")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.llm_provider == "deepseek"
    assert bool(settings.deepseek_api_key) is True
    get_settings.cache_clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_name", "expected_skills"),
    [
        ("backend_go_case.json", {"Go", "Gin", "PostgreSQL"}),
        ("backend_java_case.json", {"Java", "Spring Boot", "MySQL", "Redis"}),
        (
            "backend_python_case.json",
            {"Python", "FastAPI", "PostgreSQL", "SQLAlchemy"},
        ),
    ],
)
async def test_resume_fallback_extracts_only_literal_skills_and_no_facts(
    case_name: str, expected_skills: set[str]
) -> None:
    case = json.loads(
        (Path("tests/fixtures/sample_cases") / case_name).read_text(encoding="utf-8")
    )
    output = await ResumeAnalyzerAgent(MockLLMClient()).run(
        {"raw_text": case["resume_text"]}
    )

    assert expected_skills.issubset(set(output["skills"]))
    assert output["projects"] == []
    assert output["work_experiences"] == []
    assert output["education"] == []
    assert output["awards"] == []
    assert "简历项目" not in json.dumps(output, ensure_ascii=False, default=str)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_name", "jd_terms", "expected", "forbidden"),
    [
        ("backend_go_case.json", ["Go", "Gin"], "Go", ["FastAPI", "Java"]),
        (
            "backend_java_case.json",
            ["Java", "Spring Boot", "MySQL", "Redis"],
            "Java",
            ["FastAPI", "Go"],
        ),
        (
            "backend_python_case.json",
            ["Python", "FastAPI", "PostgreSQL"],
            "FastAPI",
            ["Spring Boot", "Gin"],
        ),
    ],
)
async def test_question_bank_fallback_is_contextual_unique_and_stack_safe(
    case_name: str,
    jd_terms: list[str],
    expected: str,
    forbidden: list[str],
) -> None:
    case = json.loads(
        (Path("tests/fixtures/sample_cases") / case_name).read_text(encoding="utf-8")
    )
    resume = await ResumeAnalyzerAgent(MockLLMClient()).run(
        {"raw_text": case["resume_text"]}
    )
    output = await QuestionBankAgent(MockLLMClient()).run(
        {
            "resume_profile": resume,
            "jd_profile": {
                "tech_keywords": jd_terms,
                "hard_requirements": jd_terms,
                "interview_focuses": ["system design"],
            },
            "match_report": {
                "preparation_priorities": [case["preparation_goal"]],
                "missing_capabilities": ["production debugging"],
            },
            "experience_profiles": [
                {"frequent_topics": [case["experience_text"]]}
            ],
            "preparation_goal": case["preparation_goal"],
        }
    )
    bank = QuestionBank.model_validate(output)
    questions = [
        *bank.self_intro_questions,
        *bank.professional_questions,
        *bank.behavior_project_questions,
    ]
    normalized = {
        re.sub(r"\s*\(\d+\)\s*$", "", question.question_text).strip().casefold()
        for question in questions
    }
    professional_text = " ".join(
        question.question_text for question in bank.professional_questions
    )

    assert len(questions) == len(normalized) == 25
    assert expected in professional_text
    assert all(term not in professional_text for term in forbidden)
    assert all(re.search(r"\(\d+\)\s*$", question.question_text) is None for question in questions)


@pytest.mark.asyncio
async def test_upstream_fallback_produces_observable_degraded_evaluation_without_call() -> None:
    client = NeverCalledProvider()
    agent = AnswerEvaluatorAgent(client)

    output = await agent.run(
        {
            "question_text": "Explain the design.",
            "user_answer": "A short answer.",
            "source_context": {
                "question": {
                    "execution_mode": "fallback",
                    "source_quality": "degraded",
                }
            },
        }
    )
    evaluation = AnswerEvaluation.model_validate(output)

    assert client.calls == 0
    assert evaluation.evaluation_mode == "degraded"
    assert evaluation.score_available is False
    assert evaluation.total_score is None
    assert evaluation.dimension_scores == []
    assert agent.last_execution.execution_mode == "fallback"
    assert agent.last_execution.real_call_count == 0
    assert agent.last_execution.retry_count == 0
    assert agent.last_execution.fallback_reason["code"] == "degraded_upstream_source"


@pytest.mark.asyncio
async def test_evaluator_provider_failure_fallback_has_no_precise_score() -> None:
    client = TimeoutProvider()
    agent = AnswerEvaluatorAgent(client)

    evaluation = AnswerEvaluation.model_validate(
        await agent.run(
            {"question_text": "Explain the design.", "user_answer": "Answer."}
        )
    )

    assert client.calls == 2
    assert evaluation.evaluation_mode == "degraded"
    assert evaluation.total_score is None
    assert evaluation.dimension_scores == []
    assert agent.last_execution.failure_counts == {"timeout": 2}


@pytest.mark.asyncio
async def test_memory_agent_skips_degraded_sources_without_provider_call() -> None:
    client = NeverCalledProvider()
    agent = MemoryAgent(client)

    update = MemoryUpdate.model_validate(
        await agent.run(
            {
                "answer_evaluation": {
                    "evaluation_mode": "degraded",
                    "score_available": False,
                },
                "source_context": {
                    "question": {
                        "execution_mode": "fallback",
                        "source_quality": "degraded",
                    }
                },
            }
        )
    )

    assert client.calls == 0
    assert update.write_decision == "skip"
    assert update.memory_items == []
    assert agent.last_execution.execution_mode == "fallback"
    assert agent.last_execution.fallback_reason["code"] == "memory_write_blocked"


def test_source_quality_aggregation_and_fallback_detection() -> None:
    context = {
        "resume": {"execution_mode": "real", "source_quality": "trusted"},
        "question": {"execution_mode": "fallback", "source_quality": "degraded"},
    }

    assert aggregate_source_quality(context) == "degraded"
    assert fallback_source_names(context) == ["question"]


def test_evaluation_and_memory_conditional_schemas_reject_hidden_degradation() -> None:
    with pytest.raises(ValidationError):
        AnswerEvaluation.model_validate(
            {
                **AnswerEvaluatorAgent(MockLLMClient())._degraded_evaluation(
                    {"question_text": "Q", "user_answer": "A"},
                    ["test"],
                ),
                "total_score": 76,
            }
        )

    with pytest.raises(ValidationError):
        MemoryUpdate.model_validate(
            {"write_decision": "skip", "skip_reason": None, "memory_items": []}
        )
