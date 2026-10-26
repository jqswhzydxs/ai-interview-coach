from collections.abc import Iterator
import json
from uuid import UUID

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.agents.answer_evaluator import AnswerEvaluatorAgent
from app.agents.harness import AgentHarness
from app.agents.llm_client import LLMJSONError, LLMRequest, LLMResponse, TokenUsage
from app.agents.mock_client import MockLLMClient
from app.core.config import get_settings
from app.db.models.agent_run import AgentRun, AgentRunStep
from app.db.models.user import User
from app.schemas.evaluation import AnswerEvaluation
from app.services.agent_run_service import AgentRunService


USER_ID = UUID("00000000-0000-0000-0000-000000000001")


class SequencedRealClient:
    provider = "deepseek"
    model_name = "acceptance-test-model"

    def __init__(self, actions: list[dict | Exception], usage: TokenUsage | None = None) -> None:
        self.actions = actions
        self.usage = usage
        self.calls = 0

    async def generate_json(self, request: LLMRequest) -> LLMResponse:
        action = self.actions[self.calls]
        self.calls += 1
        if isinstance(action, Exception):
            raise action
        return LLMResponse(
            provider=self.provider,
            model_name=self.model_name,
            content=action,
            usage=self.usage,
        )


@pytest.fixture()
def db_session(tmp_path, monkeypatch) -> Iterator[Session]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'observability.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as db:
        db.add(User(id=USER_ID, display_name="Observer", role="candidate"))
        db.commit()
        yield db
    engine.dispose()
    get_settings.cache_clear()


def valid_evaluation() -> dict:
    return AnswerEvaluatorAgent(MockLLMClient())._rule_based_evaluation(
        {
            "question_text": "Explain your backend project.",
            "user_answer": "I built an API.",
        }
    )


async def run_evaluation(db: Session, run_type: str, client: SequencedRealClient):
    return await AgentHarness().run_agent(
        db=db,
        user_id=USER_ID,
        run_type=run_type,
        agent=AnswerEvaluatorAgent(client),
        input_data={
            "question_text": "Explain your backend project.",
            "user_answer": "sensitive complete answer must not be stored",
        },
        output_schema=AnswerEvaluation,
    )


@pytest.mark.asyncio
async def test_agent_runs_persist_real_fallback_usage_and_aggregate_metrics(db_session) -> None:
    success = SequencedRealClient(
        [valid_evaluation()],
        TokenUsage(input_tokens=100, output_tokens=20, total_tokens=120),
    )
    success_result = await run_evaluation(db_session, "obs_real", success)

    json_usage = TokenUsage(input_tokens=10, output_tokens=1, total_tokens=11)
    json_failure = SequencedRealClient(
        [
            LLMJSONError("invalid", usage=json_usage),
            LLMJSONError("invalid", usage=json_usage),
        ]
    )
    json_result = await run_evaluation(db_session, "obs_json", json_failure)

    timeout_failure = SequencedRealClient(
        [TimeoutError("timeout one"), TimeoutError("timeout two")]
    )
    timeout_result = await run_evaluation(db_session, "obs_timeout", timeout_failure)

    schema_failure = SequencedRealClient(
        [{"unexpected": True}, {"unexpected": True}],
        TokenUsage(input_tokens=100, output_tokens=20, total_tokens=120),
    )
    schema_result = await run_evaluation(db_session, "obs_schema", schema_failure)

    run_ids = [
        success_result.agent_run_id,
        json_result.agent_run_id,
        timeout_result.agent_run_id,
        schema_result.agent_run_id,
    ]
    runs = list(db_session.scalars(select(AgentRun).where(AgentRun.id.in_(run_ids))).all())
    runs_by_type = {run.run_type: run for run in runs}

    real_run = runs_by_type["obs_real"]
    assert real_run.execution_mode == "real"
    assert real_run.provider == "deepseek"
    assert real_run.model_name == "acceptance-test-model"
    assert real_run.prompt_version == "answer_evaluator_v0.1"
    assert real_run.real_call_count == 1
    assert real_run.retry_count == 0
    assert real_run.total_tokens == 120
    assert real_run.fallback_reason_json == {}

    assert runs_by_type["obs_json"].fallback_reason_json == {
        "code": "invalid_json",
        "failure_type": "json",
        "stage": "response_parse",
        "attempt": 2,
    }
    assert runs_by_type["obs_timeout"].failure_counts_json == {"timeout": 2}
    assert runs_by_type["obs_schema"].failure_counts_json == {"schema": 2}
    assert all(run.execution_mode == "fallback" for run in runs if run.run_type != "obs_real")
    assert json_failure.calls == timeout_failure.calls == schema_failure.calls == 2

    fallback_steps = list(
        db_session.scalars(
            select(AgentRunStep)
            .where(AgentRunStep.agent_run_id == json_result.agent_run_id)
            .order_by(AgentRunStep.step_order)
        ).all()
    )
    assert [step.action_type for step in fallback_steps] == [
        "llm_call",
        "llm_call",
        "fallback",
    ]
    assert "sensitive complete answer" not in json.dumps(
        [step.input_json for step in fallback_steps]
    )

    metrics = AgentRunService().get_metrics(db_session, run_ids=run_ids)
    assert metrics["real_success_rate"] == 0.25
    assert metrics["fallback_rate"] == 0.75
    assert metrics["real_call_count"] == 7
    assert metrics["retry_count"] == 3
    assert metrics["failure_types"] == {"json": 2, "schema": 2, "timeout": 2}
    assert metrics["token_usage"] == {
        "input_tokens": 320,
        "output_tokens": 62,
        "total_tokens": 382,
    }
