"""Explicit experimental integration; never selected by the production service."""

from collections.abc import Callable
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from app.agents.question_bank_assembler import QuestionBankAssembler
from app.agents.question_bank_draft_agent import QuestionBankDraftAgent
from app.agents.question_bank_metadata_v2 import QuestionBankMetadataAssemblerV2
from app.schemas.question_draft import QuestionDraftBank


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSET_PATHS = (
    "app/agents/question_bank_candidate_agent.py",
    "app/agents/question_bank_draft_agent.py",
    "app/agents/question_bank_assembler.py",
    "app/agents/question_bank_metadata_v2.py",
    "app/agents/question_metadata_rules.py",
    "app/agents/question_bank_agent.py",
    "app/agents/base.py",
    "app/agents/llm_client.py",
    "app/agents/openai_compatible_client.py",
    "app/agents/prompt_loader.py",
    "app/agents/prompts/question_bank_draft_agent_v0.1.md",
    "app/schemas/question_draft.py",
    "app/schemas/question.py",
    "app/schemas/common.py",
)
VERSIONS = {"v1": "deterministic-metadata-v1", "v2": QuestionBankMetadataAssemblerV2.version}


class CandidateIntegrationError(RuntimeError):
    """A broken experiment binding must not silently select another assembler."""


def payload_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def candidate_asset_hashes() -> dict[str, str]:
    return {name: hashlib.sha256((PROJECT_ROOT / name).read_bytes()).hexdigest() for name in ASSET_PATHS}


class QuestionBankCandidateAgent(QuestionBankDraftAgent):
    """Draft protocol with required per-instance metadata selection and audit record.

    The inherited prompt, request, retry and fallback implementation is unchanged.
    Experiment runners must persist last_candidate_record separately from the API bank.
    """

    name = "question_bank_candidate_agent"

    def __init__(
        self,
        *args,
        metadata_version: str,
        assembler_factory: Callable[[], object] | None = None,
        **kwargs,
    ) -> None:
        if metadata_version not in VERSIONS:
            raise CandidateIntegrationError("Unsupported Candidate metadata version")
        super().__init__(*args, **kwargs)
        expected_type = QuestionBankAssembler if metadata_version == "v1" else QuestionBankMetadataAssemblerV2
        try:
            assembler = assembler_factory() if assembler_factory is not None else (
                QuestionBankAssembler(self._safe_fallback_agent)
                if metadata_version == "v1" else QuestionBankMetadataAssemblerV2()
            )
        except Exception as exc:
            raise CandidateIntegrationError("Candidate assembler initialization failed") from exc
        if type(assembler) is not expected_type:
            raise CandidateIntegrationError("Candidate assembler does not match the selected version")
        self.assembler = assembler
        self._bound_assembler = assembler
        self._metadata_version = metadata_version
        self._asset_hashes = candidate_asset_hashes()
        self._last_candidate_record: dict | None = None

    @property
    def metadata_version(self) -> str:
        return self._metadata_version

    @property
    def last_candidate_record(self) -> dict | None:
        return deepcopy(self._last_candidate_record)

    def _ensure_binding(self) -> None:
        if self.assembler is not self._bound_assembler:
            raise CandidateIntegrationError("Candidate assembler binding changed")
        if self.metadata_version == "v2" and self.assembler.version != VERSIONS["v2"]:
            raise CandidateIntegrationError("Candidate assembler version changed")
        if candidate_asset_hashes() != self._asset_hashes:
            raise CandidateIntegrationError("Candidate assets changed during the experiment")

    def _record(self, input_data: dict, output: dict, *, mode: str, calls: int, applied: bool, draft=None) -> None:
        self._ensure_binding()
        self._last_candidate_record = {
            "record_version": "phase-2.4c-candidate-integration-v1",
            "agent": self.name,
            "selected_metadata_version": self.metadata_version,
            "metadata_assembler_version": VERSIONS[self.metadata_version],
            "metadata_applied": applied,
            "applied_metadata_assembler_version": VERSIONS[self.metadata_version] if applied else None,
            "asset_sha256": dict(self._asset_hashes),
            "asset_manifest_sha256": payload_sha256(self._asset_hashes),
            "prompt_version": self.prompt_version,
            "input_sha256": payload_sha256(input_data),
            "draft_sha256": payload_sha256(draft) if draft is not None else None,
            "bank_sha256": payload_sha256(output),
            "execution_mode": mode,
            "provider_call_count": calls,
        }

    async def run(self, input_data: dict) -> dict:
        self._last_candidate_record = None
        self._last_execution = None
        self._ensure_binding()
        output = await super().run(input_data)
        metadata = self.last_execution
        self._record(
            input_data, output, mode=metadata.execution_mode,
            calls=metadata.real_call_count, applied=metadata.execution_mode == "real",
        )
        return output

    def replay_draft(self, draft: QuestionDraftBank, input_data: dict) -> dict:
        """Use the same selected assembler on frozen drafts, with no model request."""
        self._last_candidate_record = None
        self._last_execution = None
        self._ensure_binding()
        output = self.assembler.assemble(draft, input_data)
        self._record(input_data, output, mode="offline_replay", calls=0, applied=True, draft=draft.model_dump(mode="json"))
        return output
