"""Phase 2.4D prompt-only experiment binding; never used by production."""

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
from pathlib import Path

from app.agents.question_bank_candidate_agent import PROJECT_ROOT
from app.agents.question_bank_draft_agent import QuestionBankDraftAgent
from app.agents.question_bank_metadata_v2 import QuestionBankMetadataAssemblerV2


class QuestionDraftPromptExperimentError(RuntimeError):
    pass


@dataclass(frozen=True)
class QuestionDraftPromptAsset:
    variant: str
    prompt_version: str
    relative_path: str

    @property
    def path(self) -> Path:
        return PROJECT_ROOT / self.relative_path

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


PROMPT_ASSETS = {
    "baseline": QuestionDraftPromptAsset(
        variant="baseline",
        prompt_version="question_bank_draft_agent_v0.1",
        relative_path="app/agents/prompts/question_bank_draft_agent_v0.1.md",
    ),
    "candidate": QuestionDraftPromptAsset(
        variant="candidate",
        prompt_version="question_bank_draft_agent_v0.2",
        relative_path="app/agents/prompts/question_bank_draft_agent_v0.2.md",
    ),
}


def prompt_asset_hashes() -> dict[str, str]:
    return {variant: asset.sha256 for variant, asset in PROMPT_ASSETS.items()}


class QuestionDraftPromptExperimentAgent(QuestionBankDraftAgent):
    """One Agent implementation with an explicit prompt asset dependency."""

    name = "question_draft_prompt_experiment_agent"

    def __init__(
        self,
        *args,
        prompt_variant: str,
        expected_prompt_sha256: str | None = None,
        assembler_factory: Callable[[], object] = QuestionBankMetadataAssemblerV2,
        **kwargs,
    ) -> None:
        asset = PROMPT_ASSETS.get(prompt_variant)
        if asset is None:
            raise QuestionDraftPromptExperimentError("Unsupported prompt variant")
        super().__init__(*args, **kwargs)
        try:
            assembler = assembler_factory()
        except Exception as exc:
            raise QuestionDraftPromptExperimentError(
                "Metadata v2 assembler initialization failed"
            ) from exc
        if type(assembler) is not QuestionBankMetadataAssemblerV2:
            raise QuestionDraftPromptExperimentError(
                "Phase 2.4D requires the exact metadata v2 assembler"
            )
        actual_hash = asset.sha256
        if expected_prompt_sha256 is not None and actual_hash != expected_prompt_sha256:
            raise QuestionDraftPromptExperimentError("Prompt hash drift detected")
        self.prompt_variant = prompt_variant
        self.prompt_asset = asset
        self.prompt_version = asset.prompt_version
        self.prompt_sha256 = actual_hash
        self.assembler = assembler
        self._bound_assembler = assembler

    def assert_frozen_bindings(self) -> None:
        if self.assembler is not self._bound_assembler:
            raise QuestionDraftPromptExperimentError("Assembler binding drift detected")
        if (
            type(self.assembler) is not QuestionBankMetadataAssemblerV2
            or self.assembler.version != QuestionBankMetadataAssemblerV2.version
        ):
            raise QuestionDraftPromptExperimentError("Metadata v2 version drift detected")
        if self.prompt_version != self.prompt_asset.prompt_version:
            raise QuestionDraftPromptExperimentError("Prompt selection drift detected")
        if self.prompt_asset.sha256 != self.prompt_sha256:
            raise QuestionDraftPromptExperimentError("Prompt hash drift detected")

    async def run(self, input_data: dict) -> dict:
        self.assert_frozen_bindings()
        output = await super().run(input_data)
        self.assert_frozen_bindings()
        return output
