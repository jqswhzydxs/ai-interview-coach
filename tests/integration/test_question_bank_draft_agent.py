from uuid import UUID

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.agents.harness import AgentHarness
from app.agents.question_bank_draft_agent import QuestionBankDraftAgent
from app.db.base import Base, import_models
from app.db.models.agent_run import AgentRun, AgentRunStep
from app.db.models.user import User
from app.schemas.question import QuestionBank
from tests.unit.test_question_bank_draft_protocol import (
    FakeDraftProvider,
    _input_data,
    _valid_draft,
)


USER_ID = UUID("00000000-0000-0000-0000-000000000024")


def _session_factory():
    import_models()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.mark.asyncio
async def test_harness_persists_candidate_final_schema_and_observability() -> None:
    SessionLocal = _session_factory()
    client = FakeDraftProvider(_valid_draft())

    with SessionLocal() as db:
        db.add(User(id=USER_ID, display_name="Draft Candidate", role="candidate"))
        db.commit()
        result = await AgentHarness().run_agent(
            db=db,
            user_id=USER_ID,
            run_type="phase_2_4a_candidate",
            agent=QuestionBankDraftAgent(client),
            input_data=_input_data(),
            output_schema=QuestionBank,
        )

        run = db.get(AgentRun, result.agent_run_id)
        steps = list(
            db.scalars(
                select(AgentRunStep)
                .where(AgentRunStep.agent_run_id == result.agent_run_id)
                .order_by(AgentRunStep.step_order)
            ).all()
        )

    assert result.output.total_count == 25
    assert client.calls == 1
    assert run is not None
    assert run.status == "succeeded"
    assert run.execution_mode == "real"
    assert run.prompt_version == "question_bank_draft_agent_v0.1"
    assert run.real_call_count == 1
    assert run.retry_count == 0
    assert run.total_tokens == 200
    assert [(step.action_type, step.status) for step in steps] == [
        ("llm_call", "succeeded")
    ]


@pytest.mark.asyncio
async def test_harness_records_assembly_failures_and_phase_2_3_fallback() -> None:
    SessionLocal = _session_factory()
    unsafe_draft = _valid_draft("Go")
    unsafe_draft["professional_questions"][0]["question_text"] = (
        "How should FastAPI validate this request?"
    )
    client = FakeDraftProvider(unsafe_draft)

    with SessionLocal() as db:
        db.add(User(id=USER_ID, display_name="Draft Candidate", role="candidate"))
        db.commit()
        result = await AgentHarness().run_agent(
            db=db,
            user_id=USER_ID,
            run_type="phase_2_4a_candidate_failure",
            agent=QuestionBankDraftAgent(client),
            input_data=_input_data("Go"),
            output_schema=QuestionBank,
        )

        run = db.get(AgentRun, result.agent_run_id)
        steps = list(
            db.scalars(
                select(AgentRunStep)
                .where(AgentRunStep.agent_run_id == result.agent_run_id)
                .order_by(AgentRunStep.step_order)
            ).all()
        )

    professional_text = " ".join(
        question.question_text for question in result.output.professional_questions
    )
    assert client.calls == 2
    assert "Go" in professional_text
    assert "FastAPI" not in professional_text
    assert run is not None
    assert run.status == "succeeded"
    assert run.execution_mode == "fallback"
    assert run.real_call_count == 2
    assert run.retry_count == 1
    assert run.failure_counts_json == {"schema": 2}
    assert run.fallback_reason_json["code"] == "output_transform_validation_failed"
    assert [(step.action_type, step.status) for step in steps] == [
        ("llm_call", "failed"),
        ("llm_call", "failed"),
        ("fallback", "succeeded"),
    ]
