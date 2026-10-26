"""Protocol v5 Prompt v0.2/v0.3 bindings used only by offline-gated experiments."""

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
from pathlib import Path

from app.agents.question_bank_candidate_agent import PROJECT_ROOT
from app.agents.question_bank_draft_agent import QuestionBankDraftAgent
from app.agents.question_bank_metadata_v2 import QuestionBankMetadataAssemblerV2


class QuestionDraftPromptRecoveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class QuestionDraftPromptRecoveryAsset:
    variant: str
    prompt_version: str
    relative_path: str

    @property
    def path(self) -> Path:
        return PROJECT_ROOT / self.relative_path

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


PROMPT_RECOVERY_ASSETS = {
    "baseline": QuestionDraftPromptRecoveryAsset(
        variant="baseline",
        prompt_version="question_bank_draft_agent_v0.2",
        relative_path="app/agents/prompts/question_bank_draft_agent_v0.2.md",
    ),
    "candidate": QuestionDraftPromptRecoveryAsset(
        variant="candidate",
        prompt_version="question_bank_draft_agent_v0.3",
        relative_path="app/agents/prompts/question_bank_draft_agent_v0.3.md",
    ),
}


def prompt_recovery_asset_hashes() -> dict[str, str]:
    return {
        variant: asset.sha256 for variant, asset in PROMPT_RECOVERY_ASSETS.items()
    }


class QuestionDraftPromptRecoveryExperimentAgent(QuestionBankDraftAgent):
    """QuestionDraft agent with an explicit v5 Prompt asset dependency."""

    name = "question_draft_prompt_recovery_experiment_agent"

    def __init__(
        self,
        *args,
        prompt_variant: str,
        expected_prompt_sha256: str | None = None,
        assembler_factory: Callable[[], object] = QuestionBankMetadataAssemblerV2,
        **kwargs,
    ) -> None:
        asset = PROMPT_RECOVERY_ASSETS.get(prompt_variant)
        if asset is None:
            raise QuestionDraftPromptRecoveryError("Unsupported protocol v5 Prompt variant")
        super().__init__(*args, **kwargs)
        try:
            assembler = assembler_factory()
        except Exception as exc:
            raise QuestionDraftPromptRecoveryError(
                "Metadata v2 assembler initialization failed"
            ) from exc
        if type(assembler) is not QuestionBankMetadataAssemblerV2:
            raise QuestionDraftPromptRecoveryError(
                "Protocol v5 requires the exact metadata v2 assembler"
            )
        actual_hash = asset.sha256
        if expected_prompt_sha256 is not None and actual_hash != expected_prompt_sha256:
            raise QuestionDraftPromptRecoveryError("Prompt hash drift detected")
        self.prompt_variant = prompt_variant
        self.prompt_asset = asset
        self.prompt_version = asset.prompt_version
        self.prompt_sha256 = actual_hash
        self.assembler = assembler
        self._bound_assembler = assembler

    def assert_frozen_bindings(self) -> None:
        if self.assembler is not self._bound_assembler:
            raise QuestionDraftPromptRecoveryError("Assembler binding drift detected")
        if (
            type(self.assembler) is not QuestionBankMetadataAssemblerV2
            or self.assembler.version != QuestionBankMetadataAssemblerV2.version
        ):
            raise QuestionDraftPromptRecoveryError("Metadata v2 version drift detected")
        if self.prompt_version != self.prompt_asset.prompt_version:
            raise QuestionDraftPromptRecoveryError("Prompt selection drift detected")
        if self.prompt_asset.sha256 != self.prompt_sha256:
            raise QuestionDraftPromptRecoveryError("Prompt hash drift detected")

    async def run(self, input_data: dict) -> dict:
        self.assert_frozen_bindings()
        output = await super().run(input_data)
        self.assert_frozen_bindings()
        return output

