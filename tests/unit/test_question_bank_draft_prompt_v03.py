import hashlib

import pytest

from app.agents.mock_client import MockLLMClient
from app.agents.question_bank_agent import QuestionBankAgent
from app.agents.question_bank_metadata_v2 import QuestionBankMetadataAssemblerV2
from app.agents.question_draft_prompt_recovery_experiment import (
    PROMPT_RECOVERY_ASSETS,
    QuestionDraftPromptRecoveryError,
    QuestionDraftPromptRecoveryExperimentAgent,
    prompt_recovery_asset_hashes,
)
from app.schemas.question import QuestionBank
from app.schemas.question_draft import QuestionDraft, QuestionDraftBank
from tests.unit.test_question_bank_draft_protocol import _input_data, _valid_draft


def test_prompt_v03_contract_contains_recovery_constraints_without_stack_hardcoding():
    prompt = PROMPT_RECOVERY_ASSETS["candidate"].path.read_text(encoding="utf-8")
    required = (
        "每道题引用一个",
        "不得虚构",
        "实质性多样",
        "可训练的分析角度",
        "技术正确",
        "表达清晰",
        "每道题只保留一个主要考察目标",
        "只能包含 `question_text`",
        "恰好 8 道",
        "恰好 9 道",
        "reasoning_content",
    )
    assert all(fragment in prompt for fragment in required)
    assert all(
        term not in prompt
        for term in ("FastAPI", "Spring", "Kubernetes", "Golang", "Python", "Java")
    )


def test_v02_is_frozen_and_v03_is_a_distinct_explicit_asset():
    assert PROMPT_RECOVERY_ASSETS["baseline"].prompt_version == "question_bank_draft_agent_v0.2"
    assert PROMPT_RECOVERY_ASSETS["candidate"].prompt_version == "question_bank_draft_agent_v0.3"
    assert prompt_recovery_asset_hashes()["baseline"] == "f62170fcfab44a74c153f1c0af5195acf227ab2c8d2acce28178792890e82c4e"
    assert prompt_recovery_asset_hashes()["candidate"] == hashlib.sha256(
        PROMPT_RECOVERY_ASSETS["candidate"].path.read_bytes()
    ).hexdigest()
    assert prompt_recovery_asset_hashes()["baseline"] != prompt_recovery_asset_hashes()["candidate"]


def test_prompt_variants_share_schema_metadata_v2_and_differ_only_by_prompt_text():
    client = MockLLMClient()
    agents = {
        variant: QuestionDraftPromptRecoveryExperimentAgent(client, prompt_variant=variant)
        for variant in ("baseline", "candidate")
    }
    assert type(agents["baseline"].assembler) is type(agents["candidate"].assembler) is QuestionBankMetadataAssemblerV2
    requests = {
        variant: agent._build_request(_input_data("Go"), QuestionDraftBank)
        for variant, agent in agents.items()
    }
    assert requests["baseline"].temperature == requests["candidate"].temperature == 0.2
    assert requests["baseline"].user_prompt == requests["candidate"].user_prompt
    assert requests["baseline"].response_schema_name == requests["candidate"].response_schema_name == "QuestionDraftBank"
    normalized = {}
    for variant, request in requests.items():
        prompt = PROMPT_RECOVERY_ASSETS[variant].path.read_text(encoding="utf-8")
        assert request.system_prompt.count(prompt) == 1
        normalized[variant] = request.system_prompt.replace(prompt, "<PROMPT_TEXT>", 1)
    assert normalized["baseline"] == normalized["candidate"]


def test_draft_and_metadata_v2_keep_only_question_text_and_8_8_9_contract():
    draft = QuestionDraftBank.model_validate(_valid_draft("Go"))
    assert [len(draft.self_intro_questions), len(draft.professional_questions), len(draft.behavior_project_questions)] == [8, 8, 9]
    assert all(set(question.model_dump()) == {"question_text"} for question in (
        *draft.self_intro_questions,
        *draft.professional_questions,
        *draft.behavior_project_questions,
    ))
    assembled = QuestionBankMetadataAssemblerV2().assemble(draft, _input_data("Go"))
    bank = QuestionBank.model_validate(assembled)
    assert [len(bank.self_intro_questions), len(bank.professional_questions), len(bank.behavior_project_questions)] == [8, 8, 9]
    assert QuestionDraft.model_json_schema()["properties"]["question_text"]["maxLength"] == 500


@pytest.mark.parametrize("variant", ["", "v0.2", "v0.3", "default", None])
def test_unknown_prompt_selection_is_rejected(variant):
    with pytest.raises(QuestionDraftPromptRecoveryError, match="Unsupported"):
        QuestionDraftPromptRecoveryExperimentAgent(MockLLMClient(), prompt_variant=variant)


def test_hash_or_assembler_drift_fails_closed_and_production_default_is_unchanged():
    with pytest.raises(QuestionDraftPromptRecoveryError, match="Prompt hash drift"):
        QuestionDraftPromptRecoveryExperimentAgent(
            MockLLMClient(), prompt_variant="candidate", expected_prompt_sha256="0" * 64
        )
    with pytest.raises(QuestionDraftPromptRecoveryError, match="exact metadata v2"):
        QuestionDraftPromptRecoveryExperimentAgent(
            MockLLMClient(), prompt_variant="candidate", assembler_factory=lambda: object()
        )
    from app.services import prep_package_service

    assert prep_package_service.QuestionBankAgent is QuestionBankAgent
    assert QuestionBankAgent.prompt_version == "question_bank_agent_v0.1"
