from uuid import UUID

import pytest
from pydantic import Field
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.agents.base import BaseAgent
from app.agents.harness import AgentHarness
from app.agents.mock_client import MockLLMClient
from app.core.errors import AppError
from app.db.base import Base, import_models
from app.db.models.agent_run import AgentRun, AgentRunStep
from app.db.models.user import User
from app.schemas.common import StrictBaseModel


class HarnessOutput(StrictBaseModel):
    answer: str = Field(min_length=1)


class SuccessfulAgent(BaseAgent):
    name = "successful_agent"
    prompt_version = "successful_agent_v0.1"

    async def run(self, input_data: dict) -> dict:
        return {"answer": "ok"}


class FlakyAgent(BaseAgent):
    name = "flaky_agent"
    prompt_version = "flaky_agent_v0.1"

    def __init__(self) -> None:
        super().__init__(llm_client=MockLLMClient())
        self.calls = 0

    async def run(self, input_data: dict) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {"answer": ""}
        return {"answer": "ok after retry"}


class InvalidAgent(BaseAgent):
    name = "invalid_agent"
    prompt_version = "invalid_agent_v0.1"

    async def run(self, input_data: dict) -> dict:
        return {"answer": ""}


@pytest.fixture()
def db_session():
    import_models()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with SessionLocal() as session:
        session.add(
            User(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                display_name="Default Candidate",
                role="candidate",
            )
        )
        session.commit()
        yield session


@pytest.mark.asyncio
async def test_harness_success_writes_run_and_step(db_session) -> None:
    harness = AgentHarness()
    agent = SuccessfulAgent(llm_client=MockLLMClient())

    result = await harness.run_agent(
        db=db_session,
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        run_type="unit_test",
        agent=agent,
        input_data={"resume_text": "email test@example.com"},
        output_schema=HarnessOutput,
    )

    run = db_session.get(AgentRun, result.agent_run_id)
    steps = db_session.scalars(select(AgentRunStep).where(AgentRunStep.agent_run_id == run.id)).all()

    assert result.output.answer == "ok"
    assert run.status == "succeeded"
    assert run.provider == "mock"
    assert run.execution_mode == "mock"
    assert run.real_call_count == 0
    assert run.retry_count == 0
    assert run.input_summary_json == {"keys": ["resume_text"]}
    assert len(steps) == 1
    assert steps[0].status == "succeeded"


@pytest.mark.asyncio
async def test_harness_does_not_retry_agent_on_schema_validation_failure(db_session) -> None:
    harness = AgentHarness()
    agent = FlakyAgent()

    with pytest.raises(AppError, match="Agent output validation failed"):
        await harness.run_agent(
            db=db_session,
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            run_type="unit_test",
            agent=agent,
            input_data={"prompt": "test"},
            output_schema=HarnessOutput,
        )

    run = db_session.scalars(select(AgentRun).where(AgentRun.run_type == "unit_test")).first()
    steps = db_session.scalars(
        select(AgentRunStep)
        .where(AgentRunStep.agent_run_id == run.id)
        .order_by(AgentRunStep.step_order)
    ).all()

    assert agent.calls == 1
    assert run.status == "failed"
    assert [step.status for step in steps] == ["failed"]
    assert steps[0].action_type == "output_validation"


@pytest.mark.asyncio
async def test_harness_marks_run_failed_after_retry_exhausted(db_session) -> None:
    harness = AgentHarness()
    agent = InvalidAgent(llm_client=MockLLMClient())

    with pytest.raises(AppError, match="Agent output validation failed") as exc_info:
        await harness.run_agent(
            db=db_session,
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            run_type="unit_test",
            agent=agent,
            input_data={"prompt": "test"},
            output_schema=HarnessOutput,
        )

    run = db_session.scalars(select(AgentRun).where(AgentRun.run_type == "unit_test")).first()
    steps = db_session.scalars(select(AgentRunStep).where(AgentRunStep.agent_run_id == run.id)).all()

    assert exc_info.value.code == "AGENT_FAILED"
    assert run.status == "failed"
    assert len(steps) == 1
