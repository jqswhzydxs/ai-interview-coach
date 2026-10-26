import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agents.base import AgentOutputValidationError
from app.agents.jd_analyzer import JDAnalyzerAgent
from app.agents.llm_client import LLMRequest, LLMResponse, TokenUsage
from app.agents.mock_client import MockLLMClient
from app.agents.question_bank_agent import QuestionBankAgent
from app.agents.question_bank_assembler import (
    QuestionBankAssembler,
    normalize_question_text,
)
from app.agents.question_bank_draft_agent import QuestionBankDraftAgent
from app.schemas.question import QuestionBank
from app.schemas.question_draft import QuestionDraftBank


SAMPLE_CASE_DIR = Path("tests/fixtures/sample_cases")


class FakeDraftProvider:
    provider = "deepseek"
    model_name = "fake-draft-model"

    def __init__(self, content: dict) -> None:
        self.content = content
        self.calls = 0
        self.requests: list[LLMRequest] = []

    async def generate_json(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        self.requests.append(request)
        return LLMResponse(
            provider=self.provider,
            model_name=self.model_name,
            content=self.content,
            usage=TokenUsage(input_tokens=120, output_tokens=80, total_tokens=200),
        )


def _input_data(technology: str = "Python") -> dict:
    return {
        "resume_profile": {"skills": [technology]},
        "jd_profile": {
            "tech_keywords": [technology],
            "hard_requirements": [technology],
            "interview_focuses": ["reliability and system design"],
        },
        "match_report": {
            "preparation_priorities": ["explain design trade-offs"],
            "missing_capabilities": ["production diagnosis"],
        },
        "experience_profiles": [
            {"frequent_topics": ["incident diagnosis and recovery"]}
        ],
        "preparation_goal": "prepare for a backend engineering interview",
    }


def _valid_draft(technology: str = "Python") -> dict:
    self_intro = [
        f"Summarize the documented evidence for your {technology} backend readiness.",
        "Explain which stated role requirements best match your current capabilities.",
        "Describe a genuine experience that demonstrates careful engineering judgment.",
        "Connect your technical growth path to the responsibilities in this position.",
        "Distinguish your documented strengths from the areas that still need practice.",
        "Introduce an example where you verified quality with observable evidence.",
        "Clarify your individual contribution without claiming the entire team result.",
        "Choose one interview topic you want the interviewer to explore in depth.",
    ]
    professional = [
        f"What responsibility should {technology} own in the described backend architecture?",
        f"How would you divide interfaces, data, and failure handling around {technology}?",
        f"How would you diagnose a latency regression in a {technology} service?",
        f"Which trade-offs matter when scaling the documented {technology} workload?",
        "How would you define measurable acceptance criteria for the proposed design?",
        "Which normal, exceptional, and concurrent paths deserve automated tests?",
        "What monitoring signals would distinguish symptoms from the root cause?",
        "How would you evolve the design while limiting migration and rollback risk?",
    ]
    behavior = [
        "Describe how you clarified an ambiguous requirement and confirmed acceptance criteria.",
        "Explain how you resolved a technical disagreement using comparable evidence.",
        "Describe how you exposed a delivery risk and protected the critical commitment.",
        "Give an example of taking ownership while keeping your responsibility boundary clear.",
        "Explain a failure you reviewed and the process change that prevented recurrence.",
        "Describe cross-functional coordination where you verified shared understanding.",
        "Explain a decision that balanced delivery speed against engineering quality.",
        "Describe how you learned an unfamiliar domain and validated the result in practice.",
        "Define the next practice improvement and how you will measure real progress.",
    ]
    return {
        "self_intro_questions": [{"question_text": text} for text in self_intro],
        "professional_questions": [{"question_text": text} for text in professional],
        "behavior_project_questions": [{"question_text": text} for text in behavior],
    }


def _assembler() -> QuestionBankAssembler:
    return QuestionBankAssembler(QuestionBankAgent(MockLLMClient()))


def test_draft_schema_is_exact_8_8_9_and_forbids_computed_fields() -> None:
    draft = QuestionDraftBank.model_validate(_valid_draft())

    assert [
        len(draft.self_intro_questions),
        len(draft.professional_questions),
        len(draft.behavior_project_questions),
    ] == [8, 8, 9]

    invalid_count = _valid_draft()
    invalid_count["behavior_project_questions"].pop()
    with pytest.raises(ValidationError):
        QuestionDraftBank.model_validate(invalid_count)

    computed_field = _valid_draft()
    computed_field["self_intro_questions"][0]["question_id"] = "model-owned-id"
    with pytest.raises(ValidationError):
        QuestionDraftBank.model_validate(computed_field)


def test_draft_contract_is_materially_smaller_than_final_question_bank_contract() -> None:
    draft_schema = json.dumps(
        QuestionDraftBank.model_json_schema(), ensure_ascii=False, sort_keys=True
    )
    final_schema = json.dumps(
        QuestionBank.model_json_schema(), ensure_ascii=False, sort_keys=True
    )

    assert len(draft_schema) < len(final_schema) * 0.4
    assert "question_id" not in draft_schema
    assert "scoring_anchors" not in draft_schema
    assert "follow_up_questions" not in draft_schema


@pytest.mark.parametrize("technology", ["Python", "Go", "Java"])
def test_assembler_builds_strict_final_bank_for_each_sample_stack(
    technology: str,
) -> None:
    bank = QuestionBank.model_validate(
        _assembler().assemble(
            QuestionDraftBank.model_validate(_valid_draft(technology)),
            _input_data(technology),
        )
    )
    questions = [
        *bank.self_intro_questions,
        *bank.professional_questions,
        *bank.behavior_project_questions,
    ]

    assert [
        len(bank.self_intro_questions),
        len(bank.professional_questions),
        len(bank.behavior_project_questions),
    ] == [8, 8, 9]
    assert bank.total_count == len(questions) == 25
    assert [question.question_id for question in bank.professional_questions] == [
        f"pro-{index:02d}" for index in range(1, 9)
    ]
    assert [question.sort_order for question in bank.behavior_project_questions] == list(
        range(1, 10)
    )
    assert all(question.answer_framework for question in questions)
    assert all(question.scoring_anchors for question in questions)
    assert all(question.follow_up_questions for question in questions)
    assert all(question.preparation_advice for question in questions)
    assert all(question.source_refs for question in questions)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_name", "technology"),
    [
        ("backend_go_case.json", "Go"),
        ("backend_java_case.json", "Java"),
        ("backend_python_case.json", "Python"),
    ],
)
async def test_assembler_uses_the_three_existing_sample_case_contexts(
    case_name: str,
    technology: str,
) -> None:
    case = json.loads((SAMPLE_CASE_DIR / case_name).read_text(encoding="utf-8"))
    jd_profile = await JDAnalyzerAgent(MockLLMClient()).run(
        {"raw_text": case["jd_text"], "title": "Backend Engineer"}
    )
    input_data = {
        "resume_profile": {"skills": [technology]},
        "jd_profile": jd_profile,
        "experience_profiles": [{"frequent_topics": [case["experience_text"]]}],
        "match_report": {"preparation_priorities": [case["preparation_goal"]]},
        "preparation_goal": case["preparation_goal"],
    }

    bank = QuestionBank.model_validate(
        _assembler().assemble(
            QuestionDraftBank.model_validate(_valid_draft(technology)),
            input_data,
        )
    )

    assert bank.total_count == 25
    assert technology in " ".join(
        question.question_text for question in bank.professional_questions
    )


def test_assembler_rejects_number_only_duplicates_after_normalization() -> None:
    payload = _valid_draft()
    payload["self_intro_questions"][0]["question_text"] = (
        "Explain a documented engineering decision (1)"
    )
    payload["professional_questions"][0]["question_text"] = (
        "Explain a documented engineering decision (2)"
    )

    with pytest.raises(AgentOutputValidationError, match="normalized-unique"):
        _assembler().assemble(
            QuestionDraftBank.model_validate(payload),
            _input_data(),
        )

    assert normalize_question_text("1. Explain a documented decision (2)") == (
        "explainadocumenteddecision"
    )


def test_assembler_rejects_near_duplicates() -> None:
    payload = _valid_draft()
    payload["self_intro_questions"][0]["question_text"] = (
        "Explain how you diagnosed a difficult production latency regression."
    )
    payload["professional_questions"][0]["question_text"] = (
        "Explain how you diagnosed a difficult production latency regression?"
    )

    with pytest.raises(AgentOutputValidationError, match="normalized-unique"):
        _assembler().assemble(
            QuestionDraftBank.model_validate(payload),
            _input_data(),
        )


def test_assembler_rejects_cross_stack_technology() -> None:
    payload = _valid_draft("Go")
    payload["professional_questions"][0]["question_text"] = (
        "How would FastAPI own request validation in this service?"
    )

    with pytest.raises(AgentOutputValidationError, match="out-of-context"):
        _assembler().assemble(
            QuestionDraftBank.model_validate(payload),
            _input_data("Go"),
        )


def test_assembler_requires_resume_jd_or_experience_evidence() -> None:
    with pytest.raises(AgentOutputValidationError, match="requires resume"):
        _assembler().assemble(
            QuestionDraftBank.model_validate(_valid_draft()),
            {"preparation_goal": "generic practice"},
        )


@pytest.mark.asyncio
async def test_candidate_uses_one_call_and_returns_final_question_bank() -> None:
    client = FakeDraftProvider(_valid_draft())
    agent = QuestionBankDraftAgent(client)

    outcome = await agent.execute(_input_data())
    bank = QuestionBank.model_validate(outcome.output)

    assert client.calls == 1
    assert len(client.requests) == 1
    assert client.requests[0].response_schema_name == "QuestionDraftBank"
    assert client.requests[0].temperature == 0.2
    assert bank.total_count == 25
    assert outcome.metadata.execution_mode == "real"
    assert outcome.metadata.prompt_version == "question_bank_draft_agent_v0.1"
    assert outcome.metadata.real_call_count == 1
    assert outcome.metadata.retry_count == 0
    assert outcome.metadata.total_tokens == 200


@pytest.mark.asyncio
async def test_candidate_assembly_failure_retries_only_in_base_and_uses_safe_fallback() -> None:
    unsafe_draft = _valid_draft("Go")
    unsafe_draft["professional_questions"][0]["question_text"] = (
        "How should FastAPI validate this request?"
    )
    client = FakeDraftProvider(unsafe_draft)
    agent = QuestionBankDraftAgent(client)

    outcome = await agent.execute(_input_data("Go"))
    bank = QuestionBank.model_validate(outcome.output)
    professional_text = " ".join(
        question.question_text for question in bank.professional_questions
    )

    assert client.calls == 2
    assert "Go" in professional_text
    assert "FastAPI" not in professional_text
    assert outcome.metadata.execution_mode == "fallback"
    assert outcome.metadata.real_call_count == 2
    assert outcome.metadata.retry_count == 1
    assert outcome.metadata.failure_counts == {"schema": 2}
    assert outcome.metadata.fallback_reason == {
        "code": "output_transform_validation_failed",
        "failure_type": "schema",
        "stage": "output_transform",
        "attempt": 2,
    }


@pytest.mark.asyncio
async def test_candidate_invalid_draft_count_retries_and_uses_safe_fallback() -> None:
    invalid_draft = _valid_draft()
    invalid_draft["behavior_project_questions"].pop()
    client = FakeDraftProvider(invalid_draft)

    outcome = await QuestionBankDraftAgent(client).execute(_input_data())

    assert client.calls == 2
    assert QuestionBank.model_validate(outcome.output).total_count == 25
    assert outcome.metadata.execution_mode == "fallback"
    assert outcome.metadata.failure_counts == {"schema": 2}
    assert outcome.metadata.fallback_reason["code"] == "schema_validation_failed"
    assert outcome.metadata.fallback_reason["stage"] == "schema_validation"


def test_baseline_and_candidate_requests_are_independent_in_one_process() -> None:
    baseline = QuestionBankAgent(MockLLMClient())
    candidate = QuestionBankDraftAgent(MockLLMClient())

    baseline_request = baseline._build_request(_input_data(), QuestionBank)
    candidate_request = candidate._build_request(_input_data(), QuestionDraftBank)

    assert baseline.prompt_version == "question_bank_agent_v0.1"
    assert candidate.prompt_version == "question_bank_draft_agent_v0.1"
    assert baseline_request.response_schema_name == "QuestionBank"
    assert candidate_request.response_schema_name == "QuestionDraftBank"
    assert "question_id" in baseline_request.system_prompt
    assert "question_id" not in candidate_request.system_prompt
