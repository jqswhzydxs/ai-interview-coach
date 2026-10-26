from decimal import Decimal
import json
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.answer_evaluator import AnswerEvaluatorAgent
from app.agents.experience_analyzer import ExperienceAnalyzerAgent
from app.agents.jd_analyzer import JDAnalyzerAgent
from app.agents.llm_client import LLMRequest, LLMResponse, TokenUsage
from app.agents.matching_agent import MatchingAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.mock_client import MockLLMClient
from app.agents.question_bank_agent import QuestionBankAgent
from app.agents.question_bank_draft_agent import QuestionBankDraftAgent
from app.agents.resume_analyzer import ResumeAnalyzerAgent
from app.db.base import Base, import_models
from app.db.models.user import User
from app.services.llm_acceptance_service import LLMAcceptanceRunner
from tests.unit.test_question_bank_draft_protocol import _valid_draft


USER_ID = UUID("00000000-0000-0000-0000-000000000001")


class SchemaAwareFakeRealClient:
    provider = "kimi"
    model_name = "fake-kimi-acceptance"

    def __init__(self) -> None:
        self.calls = 0
        self.requested_schema_names: list[str | None] = []

    async def generate_json(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        self.requested_schema_names.append(request.response_schema_name)
        content_by_schema = {
            "ResumeProfile": ResumeAnalyzerAgent(MockLLMClient())._rule_based_profile(
                {"raw_text": "Python FastAPI"}
            ),
            "JDProfile": JDAnalyzerAgent(MockLLMClient())._rule_based_profile(
                {"raw_text": "Python FastAPI", "title": "Backend Engineer"}
            ),
            "ExperienceProfile": ExperienceAnalyzerAgent(
                MockLLMClient()
            )._rule_based_profile({"raw_text": "database API"}),
            "MatchReport": MatchingAgent(MockLLMClient())._rule_based_report(),
            "QuestionBank": QuestionBankAgent(
                MockLLMClient()
            )._rule_based_question_bank(),
            "QuestionDraftBank": _valid_draft(),
            "AnswerEvaluation": AnswerEvaluatorAgent(
                MockLLMClient()
            )._rule_based_evaluation(
                {"question_text": "Explain a project", "user_answer": "An answer"}
            ),
            "MemoryUpdate": MemoryAgent(MockLLMClient())._rule_based_memory_update(),
        }
        return LLMResponse(
            provider=self.provider,
            model_name=self.model_name,
            content=content_by_schema[request.response_schema_name],
            usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            raw_text="raw response that must not be reported",
        )


@pytest.mark.asyncio
async def test_acceptance_runner_uses_three_cases_and_writes_safe_reports(tmp_path) -> None:
    import_models()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    client = SchemaAwareFakeRealClient()

    with SessionLocal() as db:
        db.add(User(id=USER_ID, display_name="Acceptance", role="candidate"))
        db.commit()
        artifacts = await LLMAcceptanceRunner(
            llm_client=client,
            report_dir=tmp_path / "reports",
            input_cost_per_million=Decimal("1"),
            output_cost_per_million=Decimal("2"),
            cost_currency="TEST",
        ).run(
            db=db,
            user_id=USER_ID,
            sample_dir=Path(__file__).parents[1] / "fixtures" / "sample_cases",
        )

    assert client.calls == 21
    assert artifacts.json_path.exists()
    assert artifacts.markdown_path.exists()
    report = json.loads(artifacts.json_path.read_text(encoding="utf-8"))
    markdown = artifacts.markdown_path.read_text(encoding="utf-8")

    assert report["sample_case_count"] == 3
    assert [case["case_id"] for case in report["sample_cases"]] == [
        "backend_go_case",
        "backend_java_case",
        "backend_python_case",
    ]
    assert {case["execution_mode"] for case in report["sample_cases"]} == {"real"}
    assert report["summary"]["real_success_rate"] == 1.0
    assert report["summary"]["fallback_rate"] == 0.0
    assert report["summary"]["token_usage"] == {
        "input_tokens": 210,
        "output_tokens": 105,
        "total_tokens": 315,
    }
    assert report["cost_estimate"]["status"] == "estimated"
    assert report["cost_estimate"]["amount"] == "0.000420"

    combined_report = artifacts.json_path.read_text(encoding="utf-8") + markdown
    assert "Go backend developer" not in combined_report
    assert "raw response that must not be reported" not in combined_report
    assert "API_KEY" not in combined_report


@pytest.mark.asyncio
async def test_acceptance_runner_compares_baseline_and_candidate_in_one_process(
    tmp_path,
) -> None:
    import_models()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    client = SchemaAwareFakeRealClient()
    sample_dir = Path(__file__).parents[1] / "fixtures" / "sample_cases"

    with SessionLocal() as db:
        db.add(User(id=USER_ID, display_name="Acceptance", role="candidate"))
        db.commit()
        baseline = await LLMAcceptanceRunner(
            llm_client=client,
            report_dir=tmp_path / "baseline",
        ).run(db=db, user_id=USER_ID, sample_dir=sample_dir)
        candidate = await LLMAcceptanceRunner(
            llm_client=client,
            report_dir=tmp_path / "candidate",
            question_bank_agent_factory=QuestionBankDraftAgent,
        ).run(db=db, user_id=USER_ID, sample_dir=sample_dir)

    baseline_question_runs = [
        run
        for case in baseline.report["sample_cases"]
        for run in case["agent_runs"]
        if run["run_type"].endswith("_question_bank")
    ]
    candidate_question_runs = [
        run
        for case in candidate.report["sample_cases"]
        for run in case["agent_runs"]
        if run["run_type"].endswith("_question_bank")
    ]

    assert client.calls == 42
    assert client.requested_schema_names.count("QuestionBank") == 3
    assert client.requested_schema_names.count("QuestionDraftBank") == 3
    assert {run["prompt_version"] for run in baseline_question_runs} == {
        "question_bank_agent_v0.1"
    }
    assert {run["prompt_version"] for run in candidate_question_runs} == {
        "question_bank_draft_agent_v0.1"
    }
    assert baseline.report["summary"]["real_success_rate"] == 1.0
    assert candidate.report["summary"]["real_success_rate"] == 1.0
    assert {case["execution_mode"] for case in candidate.report["sample_cases"]} == {
        "real"
    }
    assert QuestionBankAgent.prompt_version == "question_bank_agent_v0.1"
