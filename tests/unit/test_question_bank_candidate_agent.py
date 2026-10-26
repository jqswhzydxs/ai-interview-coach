import pytest

from app.agents.base import AgentOutputValidationError
from app.agents.mock_client import MockLLMClient
from app.agents.question_bank_agent import QuestionBankAgent
from app.agents.question_bank_assembler import QuestionBankAssembler
from app.agents.question_bank_candidate_agent import (
    CandidateIntegrationError, QuestionBankCandidateAgent, candidate_asset_hashes,
    payload_sha256,
)
from app.agents.question_bank_draft_agent import QuestionBankDraftAgent
from app.agents.question_bank_metadata_v2 import QuestionBankMetadataAssemblerV2
from app.schemas.question import QuestionBank
from app.schemas.question_draft import QuestionDraftBank
from tests.unit.test_question_bank_draft_protocol import FakeDraftProvider, _input_data, _valid_draft


def test_candidate_requires_explicit_version_and_legacy_paths_remain_available():
    client = MockLLMClient()
    with pytest.raises(TypeError, match="metadata_version"):
        QuestionBankCandidateAgent(client)
    assert type(QuestionBankDraftAgent(client).assembler) is QuestionBankAssembler
    assert type(QuestionBankCandidateAgent(client, metadata_version="v1").assembler) is QuestionBankAssembler
    assert type(QuestionBankCandidateAgent(client, metadata_version="v2").assembler) is QuestionBankMetadataAssemblerV2
    from app.services import prep_package_service
    assert prep_package_service.QuestionBankAgent is QuestionBankAgent
    assert QuestionBankAgent.prompt_version == "question_bank_agent_v0.1"


@pytest.mark.parametrize("version", ["", "v3", "V2", None, "deterministic-metadata-v2"])
def test_unknown_versions_are_rejected_before_any_request(version):
    client = FakeDraftProvider(_valid_draft())
    with pytest.raises(CandidateIntegrationError, match="Unsupported"):
        QuestionBankCandidateAgent(client, metadata_version=version)
    assert client.calls == 0


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_failed_injection_terminates_without_fallback_or_provider(version):
    client = FakeDraftProvider(_valid_draft())

    def broken_factory():
        raise RuntimeError("synthetic initialization failure")

    with pytest.raises(CandidateIntegrationError, match="initialization failed"):
        QuestionBankCandidateAgent(client, metadata_version=version, assembler_factory=broken_factory)
    assert client.calls == 0


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_mismatched_injection_cannot_mix_versions(version):
    client = MockLLMClient()
    wrong = QuestionBankMetadataAssemblerV2() if version == "v1" else QuestionBankAssembler(QuestionBankAgent(client))
    with pytest.raises(CandidateIntegrationError, match="does not match"):
        QuestionBankCandidateAgent(client, metadata_version=version, assembler_factory=lambda: wrong)
    with pytest.raises(CandidateIntegrationError, match="does not match"):
        QuestionBankCandidateAgent(client, metadata_version=version, assembler_factory=lambda: None)


@pytest.mark.asyncio
async def test_candidate_v2_preserves_requests_parameters_and_provider_call_count():
    clients = [FakeDraftProvider(_valid_draft()) for _ in range(3)]
    legacy = QuestionBankDraftAgent(clients[0])
    v1 = QuestionBankCandidateAgent(clients[1], metadata_version="v1")
    v2 = QuestionBankCandidateAgent(clients[2], metadata_version="v2")
    original = await legacy.execute(_input_data())
    candidate_v1 = await v1.execute(_input_data())
    candidate_v2 = await v2.execute(_input_data())
    assert clients[0].requests == clients[1].requests == clients[2].requests
    assert [client.calls for client in clients] == [1, 1, 1]
    assert clients[2].requests[0].temperature == 0.2
    assert clients[2].requests[0].response_schema_name == "QuestionDraftBank"
    assert candidate_v1.output == original.output
    assert candidate_v2.output != original.output
    assert candidate_v2.metadata.real_call_count == original.metadata.real_call_count == 1
    assert candidate_v2.metadata.retry_count == original.metadata.retry_count == 0
    for key in ("self_intro_questions", "professional_questions", "behavior_project_questions"):
        assert [{field: q[field] for field in ("question_text", "question_id", "module", "sort_order")} for q in candidate_v2.output[key]] == [{field: q[field] for field in ("question_text", "question_id", "module", "sort_order")} for q in original.output[key]]
    assert QuestionBank.model_validate(candidate_v2.output).total_count == 25
    assert set(candidate_v2.output) == set(original.output)
    record = v2.last_candidate_record
    assert record["metadata_assembler_version"] == "deterministic-metadata-v2"
    assert record["metadata_applied"] is True
    assert record["asset_sha256"] == candidate_asset_hashes()
    assert record["asset_manifest_sha256"] == payload_sha256(record["asset_sha256"])
    assert record["bank_sha256"] == payload_sha256(candidate_v2.output)
    record["asset_sha256"].clear()
    assert v2.last_candidate_record["asset_sha256"]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["mock", "fallback"])
async def test_mock_and_fallback_keep_existing_safety_and_do_not_claim_v2(mode, monkeypatch):
    client = FakeDraftProvider(_valid_draft())
    agent = QuestionBankCandidateAgent(client, metadata_version="v2", use_real_llm=mode != "mock")

    def failed_assembly(*args):
        raise AgentOutputValidationError("synthetic unsafe assembly")

    monkeypatch.setattr(agent.assembler, "assemble", failed_assembly)
    outcome = await agent.execute(_input_data())
    expected = QuestionBankAgent(client)._rule_based_question_bank(_input_data())
    assert outcome.output == expected
    assert outcome.metadata.execution_mode == mode
    assert client.calls == (0 if mode == "mock" else 2)
    if mode == "fallback":
        assert outcome.metadata.retry_count == 1
        assert outcome.metadata.failure_counts == {"schema": 2}
        assert outcome.metadata.fallback_reason["code"] == "output_transform_validation_failed"
    record = agent.last_candidate_record
    assert record["metadata_applied"] is False
    assert record["applied_metadata_assembler_version"] is None
    assert record["metadata_assembler_version"] == "deterministic-metadata-v2"


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["binding", "assets", "version"])
async def test_binding_drift_stops_before_a_provider_request(change, monkeypatch):
    client = FakeDraftProvider(_valid_draft())
    agent = QuestionBankCandidateAgent(client, metadata_version="v2")
    if change == "binding":
        agent.assembler = QuestionBankAssembler(QuestionBankAgent(client))
    elif change == "version":
        monkeypatch.setattr(agent.assembler, "version", "wrong-version")
    else:
        monkeypatch.setattr("app.agents.question_bank_candidate_agent.candidate_asset_hashes", lambda: {})
    with pytest.raises(CandidateIntegrationError, match="changed"):
        await agent.execute(_input_data())
    assert client.calls == 0
    assert agent.last_candidate_record is None


def test_frozen_draft_failure_has_no_silent_v1_fallback_or_stale_success(monkeypatch):
    client = FakeDraftProvider(_valid_draft())
    agent = QuestionBankCandidateAgent(client, metadata_version="v2")
    draft = QuestionDraftBank.model_validate(_valid_draft())
    agent.replay_draft(draft, _input_data())
    assert agent.last_candidate_record["metadata_applied"] is True

    def broken(*args):
        raise AgentOutputValidationError("synthetic frozen assembly failure")

    monkeypatch.setattr(agent.assembler, "assemble", broken)
    with pytest.raises(AgentOutputValidationError):
        agent.replay_draft(draft, _input_data())
    assert agent.last_candidate_record is None
    assert client.calls == 0
