import hashlib

import pytest

from app.agents.mock_client import MockLLMClient
from app.agents.question_bank_agent import QuestionBankAgent
from app.agents.question_bank_metadata_v2 import QuestionBankMetadataAssemblerV2
from app.agents.question_draft_prompt_experiment import (
    PROMPT_ASSETS,
    QuestionDraftPromptExperimentAgent,
    QuestionDraftPromptExperimentError,
    prompt_asset_hashes,
)
from app.schemas.question_draft import QuestionDraft, QuestionDraftBank
from tests.unit.test_question_bank_draft_protocol import _input_data


def test_prompt_variants_are_explicit_and_share_exact_metadata_v2():
    client = MockLLMClient()
    with pytest.raises(TypeError, match="prompt_variant"):
        QuestionDraftPromptExperimentAgent(client)
    baseline = QuestionDraftPromptExperimentAgent(client, prompt_variant="baseline")
    candidate = QuestionDraftPromptExperimentAgent(client, prompt_variant="candidate")
    assert type(baseline.assembler) is type(candidate.assembler) is QuestionBankMetadataAssemblerV2
    assert baseline.assembler.version == candidate.assembler.version == "deterministic-metadata-v2"
    assert baseline.prompt_version == "question_bank_draft_agent_v0.1"
    assert candidate.prompt_version == "question_bank_draft_agent_v0.2"
    assert baseline.prompt_sha256 == prompt_asset_hashes()["baseline"]
    assert candidate.prompt_sha256 == prompt_asset_hashes()["candidate"]
    assert baseline.prompt_sha256 != candidate.prompt_sha256


def test_requests_differ_only_by_explicit_prompt_text():
    client = MockLLMClient()
    agents = {
        variant: QuestionDraftPromptExperimentAgent(client, prompt_variant=variant)
        for variant in ("baseline", "candidate")
    }
    requests = {
        variant: agent._build_request(_input_data("Go"), QuestionDraftBank)
        for variant, agent in agents.items()
    }
    assert requests["baseline"].temperature == requests["candidate"].temperature == 0.2
    assert requests["baseline"].user_prompt == requests["candidate"].user_prompt
    assert requests["baseline"].response_schema_name == requests["candidate"].response_schema_name == "QuestionDraftBank"
    normalized = {}
    for variant, request in requests.items():
        prompt = PROMPT_ASSETS[variant].path.read_text(encoding="utf-8")
        assert prompt in request.system_prompt
        normalized[variant] = request.system_prompt.replace(prompt, "<PROMPT_TEXT>", 1)
    assert normalized["baseline"] == normalized["candidate"]


@pytest.mark.parametrize("version", ["", "v0.1", "v0.2", "candidate_v2", None])
def test_unknown_prompt_selection_is_rejected(version):
    with pytest.raises(QuestionDraftPromptExperimentError, match="Unsupported"):
        QuestionDraftPromptExperimentAgent(MockLLMClient(), prompt_variant=version)


def test_prompt_hash_and_assembler_injection_fail_closed():
    client = MockLLMClient()
    with pytest.raises(QuestionDraftPromptExperimentError, match="Prompt hash drift"):
        QuestionDraftPromptExperimentAgent(
            client, prompt_variant="candidate", expected_prompt_sha256="0" * 64
        )
    with pytest.raises(QuestionDraftPromptExperimentError, match="exact metadata v2"):
        QuestionDraftPromptExperimentAgent(
            client, prompt_variant="candidate", assembler_factory=lambda: object()
        )
    with pytest.raises(QuestionDraftPromptExperimentError, match="initialization failed"):
        QuestionDraftPromptExperimentAgent(
            client, prompt_variant="candidate",
            assembler_factory=lambda: (_ for _ in ()).throw(RuntimeError("broken")),
        )


@pytest.mark.asyncio
async def test_binding_drift_stops_before_provider_call(monkeypatch):
    client = MockLLMClient()
    called = False

    async def forbidden(request):
        nonlocal called
        called = True
        raise AssertionError("binding drift must stop before generation")

    monkeypatch.setattr(client, "generate_json", forbidden)
    agent = QuestionDraftPromptExperimentAgent(client, prompt_variant="candidate")
    agent.assembler = QuestionBankMetadataAssemblerV2()
    with pytest.raises(QuestionDraftPromptExperimentError, match="binding drift"):
        await agent.execute(_input_data())
    assert called is False


def test_production_default_agent_is_unchanged():
    from app.services import prep_package_service

    assert prep_package_service.QuestionBankAgent is QuestionBankAgent
    assert QuestionBankAgent.prompt_version == "question_bank_agent_v0.1"
    assert PROMPT_ASSETS["baseline"].sha256 == hashlib.sha256(
        PROMPT_ASSETS["baseline"].path.read_bytes()
    ).hexdigest()
    assert QuestionDraft.model_json_schema()["properties"]["question_text"]["maxLength"] == 500
