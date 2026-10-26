"""Phase 2.4D prompt-only paired protocol.

The runner can be exercised with injected offline clients. Real execution is gated in
the CLI and is not part of Phase 2.4D-A.
"""

import asyncio
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from app.agents.llm_client import LLMClient, LLMRequest, LLMResponse
from app.agents.question_bank_candidate_agent import payload_sha256
from app.agents.question_draft_prompt_experiment import (
    PROMPT_ASSETS,
    QuestionDraftPromptExperimentAgent,
    prompt_asset_hashes,
)
from app.agents.question_bank_metadata_v2 import (
    QuestionBankMetadataAssemblerV2,
    collect_evidence,
)
from app.schemas.question import QuestionBank
from app.schemas.question_draft import QuestionDraftBank
from app.services.provider_failure_observability import (
    TOKEN_FIELDS,
    provider_failure_fields,
    safe_token_usage,
    usage_status,
)
from app.services.question_bank_ab_service import (
    CHECK_FAILED,
    CHECK_NOT_EVALUATED,
    CHECK_PASSED,
    EXPECTED_CASE_IDS,
    _analyze_bank,
    _load_frozen_cases,
)
from app.services.question_bank_metadata_replay import (
    _curated_questions,
    validate_evidence_quotes,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_VERSION = "phase-2.4d-question-draft-prompt-token-v1"
FROZEN_INPUT_SHA256 = "286b6f1b784ea5b675c86aa83c2dd7ea6597b6f6f04be4541033d90e779c7a1c"
MIN_COMPARABLE_PAIRS = 12
OUTPUT_TOKEN_LIMIT = 1_800
MIN_PAIRED_REDUCTION = 0.10
TEXT_SCORE_DIMENSIONS = (
    "personalization",
    "technical_correctness_and_stack_boundary",
    "coverage_and_substantive_diversity",
    "interview_training_value",
    "clarity",
)
LENGTH_RANGES = {
    "self_intro": (30, 80),
    "professional": (45, 105),
    "behavior_project": (40, 100),
}
HISTORICAL_REPORT_DIRS = (
    PROJECT_ROOT / "storage/reports/question-bank-ab-phase-2-4b-v2-20261019-run2",
    PROJECT_ROOT / "storage/reports/question-bank-metadata-phase-2-4c-offline-20261020",
    PROJECT_ROOT / "storage/reports/question-bank-candidate-integration-phase-2-4c-20261021",
)
COMMON_ASSETS = {
    "experiment_agent": PROJECT_ROOT / "app/agents/question_draft_prompt_experiment.py",
    "draft_agent": PROJECT_ROOT / "app/agents/question_bank_draft_agent.py",
    "base_agent": PROJECT_ROOT / "app/agents/base.py",
    "prompt_loader": PROJECT_ROOT / "app/agents/prompt_loader.py",
    "metadata_v2_assembler": PROJECT_ROOT / "app/agents/question_bank_metadata_v2.py",
    "metadata_rules": PROJECT_ROOT / "app/agents/question_metadata_rules.py",
    "assembler_checks": PROJECT_ROOT / "app/agents/question_bank_assembler.py",
    "final_schema": PROJECT_ROOT / "app/schemas/question.py",
    "draft_schema": PROJECT_ROOT / "app/schemas/question_draft.py",
    "llm_contract": PROJECT_ROOT / "app/agents/llm_client.py",
    "provider_client": PROJECT_ROOT / "app/agents/openai_compatible_client.py",
    "deepseek_client": PROJECT_ROOT / "app/agents/deepseek_client.py",
    "kimi_client": PROJECT_ROOT / "app/agents/kimi_client.py",
    "provider_config": PROJECT_ROOT / "app/core/config.py",
    "provider_observability": PROJECT_ROOT / "app/services/provider_failure_observability.py",
    "analysis_checks": PROJECT_ROOT / "app/services/question_bank_ab_service.py",
    "evidence_checks": PROJECT_ROOT / "app/services/question_bank_metadata_replay.py",
    "runner": PROJECT_ROOT / "app/services/question_draft_token_experiment.py",
    "production_agent": PROJECT_ROOT / "app/agents/question_bank_agent.py",
    "production_route": PROJECT_ROOT / "app/services/prep_package_service.py",
}


class QuestionDraftTokenExperimentError(RuntimeError):
    pass


class QuestionDraftTokenExperimentLockError(QuestionDraftTokenExperimentError):
    pass


class QuestionDraftTokenExperimentProtocolError(QuestionDraftTokenExperimentError):
    pass


class QuestionDraftTokenExperimentBudgetError(QuestionDraftTokenExperimentError):
    pass


@dataclass(frozen=True)
class QuestionDraftTokenExperimentConfig:
    input_path: Path
    run_dir: Path
    repetitions_per_case: int = 5
    execution_deadline_seconds: float = 120.0
    temperature: float = 0.2
    max_attempts: int = 2
    max_provider_calls: int = 62
    max_total_tokens: int = 250_000
    lock_path: Path | None = None

    def __post_init__(self) -> None:
        if self.repetitions_per_case != 5:
            raise ValueError("Phase 2.4D requires exactly five pairs per case")
        if not 0 < self.execution_deadline_seconds <= 120:
            raise ValueError("Variant deadline must be in (0, 120] seconds")
        if self.temperature != 0.2:
            raise ValueError("Phase 2.4D freezes temperature at 0.2")
        if self.max_attempts != 2:
            raise ValueError("Phase 2.4D freezes two Agent attempts")
        if self.max_provider_calls < 1 or self.max_total_tokens < 1:
            raise ValueError("Experiment budgets must be positive")


@dataclass(frozen=True)
class QuestionDraftTokenExperimentArtifacts:
    manifest_path: Path
    report_path: Path
    report_markdown_path: Path
    blind_packet_path: Path
    review_template_path: Path
    report: dict


class _MeasuredClient:
    def __init__(self, delegate: LLMClient, runner: "QuestionDraftTokenExperimentRunner") -> None:
        self.delegate = delegate
        self.runner = runner
        self.provider = delegate.provider
        self.model_name = delegate.model_name

    async def generate_json(self, request: LLMRequest) -> LLMResponse:
        if len(self.runner._manifest["provider_calls"]) >= self.runner.config.max_provider_calls:
            raise QuestionDraftTokenExperimentBudgetError("Provider call budget exhausted")
        call = {
            "call": len(self.runner._manifest["provider_calls"]) + 1,
            "variant": self.runner._provider_context.get("variant"),
            "case_id": self.runner._provider_context.get("case_id"),
            "pair": self.runner._provider_context.get("pair"),
            "started_at": self.runner._iso_now(),
        }
        started = perf_counter()
        try:
            response = await self.delegate.generate_json(request)
        except BaseException as exc:
            usage = safe_token_usage(getattr(exc, "usage", None))
            call.update({
                "status": "failed",
                "latency_ms": _elapsed_ms(started),
                "token_usage": usage,
                "token_usage_status": _execution_usage_status(usage),
                **provider_failure_fields(exc, sensitive_values=(request.system_prompt, request.user_prompt)),
            })
            self.runner._manifest["provider_calls"].append(call)
            self.runner._persist()
            raise
        usage = safe_token_usage(response.usage)
        call.update({
            "status": "succeeded",
            "latency_ms": _elapsed_ms(started),
            "token_usage": usage,
            "token_usage_status": _execution_usage_status(usage),
            "failure_category": None,
            "exception_type": None,
            "http_status_code": None,
            "provider_error_code": None,
            "request_id": None,
            "retry_after": None,
            "filtered_fields": [],
        })
        self.runner._manifest["provider_calls"].append(call)
        self.runner._persist()
        return response


class QuestionDraftTokenExperimentRunner:
    def __init__(self, *, llm_client: LLMClient, config: QuestionDraftTokenExperimentConfig) -> None:
        self.llm_client = llm_client
        self.config = config
        self.manifest_path = config.run_dir / "manifest.json"
        self.report_path = config.run_dir / "question-draft-token-report.json"
        self.report_markdown_path = config.run_dir / "question-draft-token-report.md"
        self.blind_packet_path = config.run_dir / "blind-review/question-review-packet.json"
        self.review_template_path = config.run_dir / "blind-review/question-review-template.json"
        self.audit_path = config.run_dir / "audit/executions.json"
        self.private_map_path = config.run_dir / "audit/private-blinding-map.json"
        self.lock_path = config.lock_path or config.run_dir.parent / ".question-draft-token.lock"
        self._provider_context: dict[str, Any] = {}
        self._measured_client = _MeasuredClient(llm_client, self)
        self._assert_run_dir_is_separate()
        self._load_or_initialize()

    def prepare(self) -> QuestionDraftTokenExperimentArtifacts:
        """Create or validate the preregistered plan without a Provider call."""
        with self._exclusive_lock("prepare"):
            self._assert_assets_unchanged()
            self._persist()
            return self._artifacts()

    async def run_smoke(self) -> QuestionDraftTokenExperimentArtifacts:
        with self._exclusive_lock("smoke"):
            self._assert_assets_unchanged()
            if self._manifest.get("smoke") is not None:
                return self._artifacts()
            case = self._cases[0]
            record, bank = await self._execute_variant(
                case=case, pair=0, variant="candidate", execution_order=1, stage="smoke"
            )
            self._manifest["smoke"] = _public_run(record)
            self._manifest["smoke_audit"] = record
            budget = self._budget_summary()
            smoke_passed = (
                _safe_real_run(record)
                and record["usage_complete"]
                and budget["known_total_tokens"] <= self.config.max_total_tokens
            )
            self._manifest["status"] = "smoke_passed" if smoke_passed else "smoke_failed"
            self._manifest["stop_reason"] = (
                None if smoke_passed
                else "smoke_usage_unknown" if not record["usage_complete"]
                else "smoke_token_budget_exceeded" if budget["known_total_tokens"] > self.config.max_total_tokens
                else "smoke_not_real_safe"
            )
            self._assert_assets_unchanged()
            self._persist()
            return self._artifacts()

    async def run_pilot(self) -> QuestionDraftTokenExperimentArtifacts:
        with self._exclusive_lock("pilot"):
            self._assert_assets_unchanged()
            if self._manifest["status"] not in {"smoke_passed", "pilot_passed", "pilot_failed"}:
                raise QuestionDraftTokenExperimentProtocolError("A passed smoke is required before pilot")
            if self._manifest["status"] in {"pilot_passed", "pilot_failed"}:
                return self._artifacts()
            completed = await self._run_pairs((1,))
            candidate = [r for r in self._manifest["runs"] if r["variant"] == "candidate" and r["pair"] == 1]
            pilot_passed = completed and len(candidate) == 3 and all(_safe_real_run(r) for r in candidate)
            self._manifest["status"] = "pilot_passed" if pilot_passed else "pilot_failed"
            self._manifest["stop_reason"] = None if pilot_passed else self._manifest.get("stop_reason") or "pilot_candidate_not_3_of_3_real_safe"
            self._assert_assets_unchanged()
            self._persist()
            return self._artifacts()

    async def run_full(self) -> QuestionDraftTokenExperimentArtifacts:
        with self._exclusive_lock("full"):
            self._assert_assets_unchanged()
            if self._manifest["status"] == "execution_completed":
                return self._artifacts()
            if self._manifest["status"] != "pilot_passed":
                raise QuestionDraftTokenExperimentProtocolError("A passed pilot is required before full")
            completed = await self._run_pairs(range(2, 6))
            if completed and len(self._manifest["runs"]) == 30:
                self._manifest["status"] = "execution_completed"
                self._manifest["completion_status"] = "awaiting_independent_blind_review"
                self._manifest["stop_reason"] = None
            elif self._manifest["status"] == "pilot_passed":
                self._manifest["status"] = "incomplete_execution"
                self._manifest["stop_reason"] = self._manifest.get("stop_reason") or "paired_execution_incomplete"
            self._assert_assets_unchanged()
            self._persist()
            return self._artifacts()

    def apply_blind_review(self, review_path: Path) -> QuestionDraftTokenExperimentArtifacts:
        with self._exclusive_lock("finalize"):
            self._assert_assets_unchanged()
            if self._manifest["status"] not in {"execution_completed", "completed"}:
                raise QuestionDraftTokenExperimentProtocolError("Full execution must complete before review")
            if self._manifest["status"] == "completed":
                return self._artifacts()
            review = json.loads(review_path.read_text(encoding="utf-8"))
            expected = [s["submission_id"] for s in self._blind_submissions()]
            supplied = review.get("submissions")
            if not isinstance(supplied, list) or [s.get("submission_id") for s in supplied] != expected:
                raise QuestionDraftTokenExperimentProtocolError("Blind review IDs or order do not match")
            evaluator = review.get("evaluator")
            if review.get("review_version") != PROTOCOL_VERSION + "-independent-review-v1":
                raise QuestionDraftTokenExperimentProtocolError("Blind review version does not match")
            if not (
                isinstance(evaluator, dict)
                and evaluator.get("type") in {"AI", "human"}
                and isinstance(evaluator.get("identifier"), str)
                and evaluator["identifier"].strip()
                and evaluator.get("independence_confirmed") is True
            ):
                raise QuestionDraftTokenExperimentProtocolError("Independent evaluator metadata is incomplete")
            validated = []
            for row in supplied:
                text_scores = row.get("text_scores")
                metadata_scores = row.get("metadata_fit_scores")
                if not (
                    isinstance(text_scores, dict)
                    and set(text_scores) == set(TEXT_SCORE_DIMENSIONS)
                    and all(_score(value) for value in text_scores.values())
                    and isinstance(metadata_scores, list)
                    and len(metadata_scores) == 25
                    and all(_score(value) for value in metadata_scores)
                ):
                    raise QuestionDraftTokenExperimentProtocolError("Blind review scores are incomplete")
                validated.append({
                    "submission_id": row["submission_id"],
                    "text_scores": text_scores,
                    "metadata_fit_scores": metadata_scores,
                })
            self._manifest["review"] = {
                "review_version": review.get("review_version"),
                "evaluator": evaluator,
                "submissions": validated,
                "source_sha256": _sha256(review_path),
            }
            self._manifest["status"] = "completed"
            self._manifest["completion_status"] = "complete"
            self._manifest["completed_at"] = self._iso_now()
            self._persist()
            return self._artifacts()

    async def _run_pairs(self, pairs: Iterator[int] | range | tuple[int, ...]) -> bool:
        existing = {(r["case_id"], r["pair"], r["variant"]) for r in self._manifest["runs"]}
        for pair in pairs:
            for case in self._cases:
                pair_records = []
                for order, variant in enumerate(_variant_order(pair), 1):
                    key = (case["case_id"], pair, variant)
                    if key in existing:
                        pair_records.append(next(r for r in self._manifest["runs"] if (r["case_id"], r["pair"], r["variant"]) == key))
                        continue
                    if len(self._manifest["provider_calls"]) + self.config.max_attempts > self.config.max_provider_calls:
                        self._manifest["status"] = "incomplete_call_budget"
                        self._manifest["stop_reason"] = "insufficient_provider_call_budget"
                        return False
                    record, bank = await self._execute_variant(
                        case=case, pair=pair, variant=variant,
                        execution_order=order, stage="paired",
                    )
                    self._manifest["runs"].append(record)
                    pair_records.append(record)
                    if bank is not None:
                        self._append_blind_submission(record, bank, case["input"])
                    existing.add(key)
                    self._persist()
                if len(pair_records) == 2:
                    invariants = {r["request_invariant_sha256"] for r in pair_records}
                    if len(invariants) != 1:
                        self._manifest["status"] = "invalidated_protocol"
                        self._manifest["stop_reason"] = "prompt_was_not_the_only_request_variable"
                        self._persist()
                        return False
                budget = self._budget_summary()
                if budget["known_total_tokens"] > self.config.max_total_tokens:
                    self._manifest["status"] = "incomplete_token_budget"
                    self._manifest["stop_reason"] = "known_token_budget_exceeded"
                    self._persist()
                    return False
                if not budget["usage_complete"]:
                    self._manifest["status"] = "incomplete_usage_unknown"
                    self._manifest["stop_reason"] = "token_budget_not_verifiable"
                    self._persist()
                    return False
        return True

    async def _execute_variant(
        self, *, case: dict, pair: int, variant: str,
        execution_order: int, stage: str,
    ) -> tuple[dict, QuestionBank | None]:
        expected_hash = self._manifest["prompt_assets"][variant]["sha256"]
        agent = QuestionDraftPromptExperimentAgent(
            self._measured_client,
            prompt_variant=variant,
            expected_prompt_sha256=expected_hash,
            max_real_llm_attempts=self.config.max_attempts,
            use_real_llm=True,
        )
        request = agent._build_request(case["input"], QuestionDraftBank)
        prompt_text = agent.prompt_asset.path.read_text(encoding="utf-8")
        if (
            request.temperature != self.config.temperature
            or request.response_schema_name != "QuestionDraftBank"
            or prompt_text not in request.system_prompt
            or agent.max_real_llm_attempts != self.config.max_attempts
        ):
            raise QuestionDraftTokenExperimentProtocolError("Frozen request parameters drifted")
        invariant_request = request.model_dump(mode="json")
        invariant_request["system_prompt"] = invariant_request["system_prompt"].replace(prompt_text, "<PROMPT_TEXT>", 1)
        request_invariant = payload_sha256(invariant_request)
        calls_before = len(self._manifest["provider_calls"])
        started_at = self._iso_now()
        started = perf_counter()
        bank = None
        metadata = None
        output_received = False
        terminal_status = "completed"
        runner_failures: Counter[str] = Counter()
        self._provider_context = {"variant": variant, "case_id": case["case_id"], "pair": pair}
        try:
            async with asyncio.timeout(self.config.execution_deadline_seconds):
                outcome = await agent.execute(case["input"])
                metadata = outcome.metadata
                output_received = True
                try:
                    bank = QuestionBank.model_validate(outcome.output)
                except Exception:
                    terminal_status = "failed"
                    runner_failures["schema"] += 1
        except TimeoutError:
            terminal_status = "deadline"
            runner_failures["deadline"] += 1
        except Exception:
            terminal_status = "failed"
            runner_failures["runner"] += 1
        calls = self._manifest["provider_calls"][calls_before:]
        usage, known_usage, run_usage_status = _aggregate_call_usage(calls)
        analysis = _analyze_bank(bank, case["input"]) if bank is not None else None
        evidence_safe = False
        if bank is not None and metadata is not None and metadata.execution_mode == "real":
            try:
                validate_evidence_quotes(bank.model_dump(mode="json"), case["input"])
                evidence_safe = True
            except Exception:
                runner_failures["evidence"] += 1
        failures = Counter(metadata.failure_counts if metadata is not None else {})
        failures.update(runner_failures)
        execution_mode = metadata.execution_mode if metadata is not None else None
        assembler_status = (
            CHECK_PASSED
            if execution_mode == "real" and evidence_safe
            else CHECK_FAILED
            if metadata is not None and metadata.fallback_reason.get("stage") == "output_transform"
            else CHECK_NOT_EVALUATED
        )
        lengths = _length_diagnostics(bank)
        record = {
            "sequence": len(self._manifest["runs"]) + 1 if stage == "paired" else 0,
            "stage": stage,
            "variant": variant,
            "case_id": case["case_id"],
            "pair": pair,
            "execution_order": execution_order,
            "started_at": started_at,
            "finished_at": self._iso_now(),
            "terminal_status": terminal_status,
            "execution_mode": execution_mode,
            "provider_calls": len(calls),
            "retry_count": max(0, len(calls) - 1),
            "failure_types": dict(sorted(failures.items())),
            "latency_ms": _elapsed_ms(started),
            "token_usage": usage,
            "known_token_usage": known_usage,
            "token_usage_status": run_usage_status,
            "usage_complete": run_usage_status == "available",
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "total_tokens": usage["total_tokens"],
            "prompt_version": agent.prompt_version,
            "prompt_sha256": agent.prompt_sha256,
            "metadata_assembler_version": agent.assembler.version,
            "metadata_v2_applied": execution_mode == "real" and assembler_status == CHECK_PASSED,
            "request_invariant_sha256": request_invariant,
            "request_schema": request.response_schema_name,
            "temperature": request.temperature,
            "max_tokens": None,
            "input_sha256": payload_sha256(case["input"]),
            "output_fingerprint": payload_sha256(bank.model_dump(mode="json")) if bank else None,
            "question_text_fingerprint": _question_text_fingerprint(bank),
            "output_received": output_received,
            "final_schema_passed": CHECK_PASSED if bank is not None else CHECK_FAILED if output_received else CHECK_NOT_EVALUATED,
            "assembler_passed": assembler_status,
            "strict_count_passed": _status(analysis["strict_count_passed"]) if analysis else CHECK_NOT_EVALUATED,
            "stack_boundary_passed": _status(analysis["stack_boundary_passed"]) if analysis else CHECK_NOT_EVALUATED,
            "cross_stack_terms": analysis["cross_stack_terms"] if analysis else [],
            "duplicate_check_passed": _status(analysis["duplicate_check_passed"]) if analysis else CHECK_NOT_EVALUATED,
            "exact_duplicate_count": analysis["exact_duplicate_count"] if analysis else None,
            "near_duplicate_pair_count": analysis["near_duplicate_pair_count"] if analysis else None,
            "length_diagnostics": lengths,
            "submission_id": f"submission-{uuid4().hex}" if bank is not None and stage == "paired" else None,
            "input": case["input"],
            "output": bank.model_dump(mode="json") if bank else None,
        }
        return record, bank

    def _append_blind_submission(self, record: dict, bank: QuestionBank, input_data: dict) -> None:
        self._manifest["submissions"].append({
            "submission_id": record["submission_id"],
            "blind_order": uuid4().hex,
            "variant": record["variant"],
            "case_id": record["case_id"],
            "pair": record["pair"],
            "evidence_context": [
                {"source_type": item.source_type, "field_path": item.path, "quote": item.value, "kind": item.kind}
                for item in collect_evidence(input_data)
            ],
            "questions": _curated_questions(bank.model_dump(mode="json")),
        })

    def _load_or_initialize(self) -> None:
        self.config.run_dir.mkdir(parents=True, exist_ok=True)
        if _sha256(self.config.input_path) != FROZEN_INPUT_SHA256:
            raise QuestionDraftTokenExperimentProtocolError("Phase 2.4D frozen input hash mismatch")
        self._cases = _load_frozen_cases(self.config.input_path)
        common_assets = _hash_assets(COMMON_ASSETS)
        prompt_assets = {
            variant: {
                "prompt_version": asset.prompt_version,
                "path": asset.relative_path,
                "sha256": asset.sha256,
            }
            for variant, asset in PROMPT_ASSETS.items()
        }
        if self.manifest_path.exists():
            try:
                manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise QuestionDraftTokenExperimentProtocolError("Manifest is unreadable") from exc
            expected = {
                "protocol_version": PROTOCOL_VERSION,
                "provider": self.llm_client.provider,
                "model": self.llm_client.model_name,
                "input_sha256": _sha256(self.config.input_path),
                "common_assets": common_assets,
                "prompt_assets": prompt_assets,
                "protocol": self._protocol_snapshot(),
            }
            for key, value in expected.items():
                if manifest.get(key) != value:
                    raise QuestionDraftTokenExperimentProtocolError(f"Manifest {key} drift detected")
            self._manifest = manifest
            return
        existing = [p for p in self.config.run_dir.rglob("*") if p.is_file()]
        if existing:
            raise QuestionDraftTokenExperimentProtocolError("New run directory must be empty")
        self._manifest = {
            "protocol_version": PROTOCOL_VERSION,
            "experiment_id": f"phase-2-4d-{uuid4().hex}",
            "created_at": self._iso_now(),
            "status": "prepared_offline",
            "completion_status": "not_started",
            "stop_reason": None,
            "provider": self.llm_client.provider,
            "model": self.llm_client.model_name,
            "input_path": self.config.input_path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(),
            "input_sha256": _sha256(self.config.input_path),
            "common_assets": common_assets,
            "prompt_assets": prompt_assets,
            "protocol": self._protocol_snapshot(),
            "phase_2_4b_interpretation": "immutable_historical_result_not_rewritten",
            "production_default_changed": False,
            "smoke": None,
            "smoke_audit": None,
            "runs": [],
            "submissions": [],
            "provider_calls": [],
            "review": None,
        }
        self._persist()

    def _protocol_snapshot(self) -> dict:
        return {
            "unique_variable": "QuestionDraft prompt text",
            "baseline_prompt": "question_bank_draft_agent_v0.1",
            "candidate_prompt": "question_bank_draft_agent_v0.2",
            "metadata_assembler": QuestionBankMetadataAssemblerV2.version,
            "pilot": "3 cases x 2 variants x pair 1",
            "full": "3 cases x 5 pairs x 2 variants = 30 runs including pilot",
            "order": "odd baseline-candidate; even candidate-baseline",
            "temperature": self.config.temperature,
            "max_tokens": None,
            "provider_client_timeout_seconds": 60,
            "max_attempts": self.config.max_attempts,
            "variant_deadline_seconds": self.config.execution_deadline_seconds,
            "max_provider_calls": self.config.max_provider_calls,
            "max_total_tokens": self.config.max_total_tokens,
            "minimum_comparable_pairs": MIN_COMPARABLE_PAIRS,
            "candidate_average_output_tokens_lte": OUTPUT_TOKEN_LIMIT,
            "paired_output_token_reduction_gte": MIN_PAIRED_REDUCTION,
            "length_ranges": {k: list(v) for k, v in LENGTH_RANGES.items()},
            "length_is_diagnostic_only": True,
            "question_draft_max_length": 500,
        }

    def _assert_run_dir_is_separate(self) -> None:
        target = self.config.run_dir.resolve()
        for protected in HISTORICAL_REPORT_DIRS:
            source = protected.resolve()
            if target == source or target.is_relative_to(source) or source.is_relative_to(target):
                raise QuestionDraftTokenExperimentProtocolError("Run directory overlaps a historical experiment")

    def _assert_assets_unchanged(self) -> None:
        if self._manifest["common_assets"] != _hash_assets(COMMON_ASSETS):
            raise QuestionDraftTokenExperimentProtocolError("Common asset drift detected")
        current = prompt_asset_hashes()
        expected = {variant: item["sha256"] for variant, item in self._manifest["prompt_assets"].items()}
        if current != expected:
            raise QuestionDraftTokenExperimentProtocolError("Prompt hash drift detected")
        if _sha256(self.config.input_path) != self._manifest["input_sha256"]:
            raise QuestionDraftTokenExperimentProtocolError("Input fixture drift detected")

    def _budget_summary(self) -> dict:
        calls = self._manifest["provider_calls"]
        complete = bool(calls) and all(c["token_usage_status"] == "available" for c in calls)
        known = {
            key: sum(c["token_usage"].get(key) or 0 for c in calls)
            for key in TOKEN_FIELDS
        }
        return {
            "provider_calls_used": len(calls),
            "provider_calls_limit": self.config.max_provider_calls,
            "usage_complete": complete,
            "total_tokens_used": known["total_tokens"] if complete else None,
            "known_total_tokens": known["total_tokens"],
            "max_total_tokens": self.config.max_total_tokens,
            "unknown_usage_calls": sum(c["token_usage_status"] != "available" for c in calls),
        }

    def _persist(self) -> None:
        self.config.run_dir.mkdir(parents=True, exist_ok=True)
        report = self._build_report()
        _atomic_json(self.manifest_path, self._manifest)
        _atomic_json(self.report_path, report)
        _atomic_text(self.report_markdown_path, _render_markdown(report))
        _atomic_json(self.audit_path, {
            "protocol_version": PROTOCOL_VERSION,
            "smoke": self._manifest.get("smoke_audit"),
            "runs": self._manifest["runs"],
            "provider_calls": self._manifest["provider_calls"],
        })
        _atomic_json(self.private_map_path, {
            "mapping": [
                {key: row[key] for key in ("submission_id", "variant", "case_id", "pair")}
                for row in self._manifest["submissions"]
            ]
        })
        _atomic_json(self.blind_packet_path, {
            "packet_version": PROTOCOL_VERSION + "-blind-packet",
            "submissions": [
                {key: row[key] for key in ("submission_id", "evidence_context", "questions")}
                for row in self._blind_submissions()
            ],
        })
        _atomic_json(self.review_template_path, {
            "review_version": PROTOCOL_VERSION + "-independent-review-v1",
            "evaluator": {"type": None, "identifier": None, "independence_confirmed": None},
            "submissions": [
                {
                    "submission_id": row["submission_id"],
                    "text_scores": {key: None for key in TEXT_SCORE_DIMENSIONS},
                    "metadata_fit_scores": [None] * 25,
                }
                for row in self._blind_submissions()
            ],
        })

    def _blind_submissions(self) -> list[dict]:
        return sorted(self._manifest["submissions"], key=lambda row: row["blind_order"])

    def _build_report(self) -> dict:
        public_runs = [_public_run(r) for r in self._manifest["runs"]]
        summary = _summary(public_runs, self._manifest.get("review"), self._manifest["submissions"])
        return {
            "protocol_version": PROTOCOL_VERSION,
            "experiment_id": self._manifest["experiment_id"],
            "status": self._manifest["status"],
            "completion_status": self._manifest["completion_status"],
            "stop_reason": self._manifest.get("stop_reason"),
            "provider": self._manifest["provider"],
            "model": self._manifest["model"],
            "prompt_assets": self._manifest["prompt_assets"],
            "protocol": self._manifest["protocol"],
            "phase_2_4b_interpretation": self._manifest["phase_2_4b_interpretation"],
            "production_default_changed": False,
            "smoke": self._manifest.get("smoke"),
            "runs": public_runs,
            "budget": self._budget_summary(),
            "summary": summary,
            "thresholds": _thresholds(public_runs, summary, self._manifest.get("review")),
            "review": (
                {"evaluator": self._manifest["review"]["evaluator"], "source_sha256": self._manifest["review"]["source_sha256"]}
                if self._manifest.get("review") else None
            ),
        }

    def _artifacts(self) -> QuestionDraftTokenExperimentArtifacts:
        return QuestionDraftTokenExperimentArtifacts(
            manifest_path=self.manifest_path,
            report_path=self.report_path,
            report_markdown_path=self.report_markdown_path,
            blind_packet_path=self.blind_packet_path,
            review_template_path=self.review_template_path,
            report=self._build_report(),
        )

    @contextmanager
    def _exclusive_lock(self, phase: str):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise QuestionDraftTokenExperimentLockError("Another token experiment process holds the lock") from exc
        try:
            os.write(descriptor, f"{os.getpid()}:{phase}".encode())
            os.close(descriptor)
            yield
        finally:
            try:
                self.lock_path.unlink()
            except FileNotFoundError:
                pass

    @staticmethod
    def _iso_now() -> str:
        return datetime.now(timezone.utc).isoformat()


def _variant_order(pair: int) -> tuple[str, str]:
    return ("baseline", "candidate") if pair % 2 else ("candidate", "baseline")


def _safe_real_run(run: dict) -> bool:
    return (
        run["terminal_status"] == "completed"
        and run["execution_mode"] == "real"
        and run["final_schema_passed"] == CHECK_PASSED
        and run["assembler_passed"] == CHECK_PASSED
        and run["strict_count_passed"] == CHECK_PASSED
        and run["stack_boundary_passed"] == CHECK_PASSED
        and run["duplicate_check_passed"] == CHECK_PASSED
    )


def _valid_token_run(run: dict) -> bool:
    return _safe_real_run(run) and run["usage_complete"] and run["output_tokens"] is not None


def _aggregate_call_usage(calls: list[dict]) -> tuple[dict, dict, str]:
    known = {key: sum(c["token_usage"].get(key) or 0 for c in calls) for key in TOKEN_FIELDS}
    if not calls:
        return ({key: None for key in TOKEN_FIELDS}, known, "not_available")
    if all(c["token_usage_status"] == "available" for c in calls):
        return (known, known, "available")
    return ({key: None for key in TOKEN_FIELDS}, known, "unknown")


def _execution_usage_status(usage: dict) -> str:
    return "available" if usage_status(usage) == "available" else "unknown"


def _length_diagnostics(bank: QuestionBank | None) -> dict | None:
    if bank is None:
        return None
    modules = {
        "self_intro": bank.self_intro_questions,
        "professional": bank.professional_questions,
        "behavior_project": bank.behavior_project_questions,
    }
    result: dict[str, Any] = {"by_module": {}}
    all_values = []
    for module, questions in modules.items():
        values = [len(q.question_text) for q in questions]
        all_values.extend(values)
        low, high = LENGTH_RANGES[module]
        result["by_module"][module] = {
            **_distribution(values),
            "character_counts": values,
            "recommended_min": low,
            "recommended_max": high,
            "below_recommended": sum(v < low for v in values),
            "above_recommended": sum(v > high for v in values),
        }
    result["overall"] = {**_distribution(all_values), "character_counts": all_values}
    result["above_module_recommended_total"] = sum(
        row["above_recommended"] for row in result["by_module"].values()
    )
    return result


def _distribution(values: list[int]) -> dict:
    return {
        "count": len(values),
        "average": sum(values) / len(values) if values else None,
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
        "max": max(values) if values else None,
    }


def _question_text_fingerprint(bank: QuestionBank | None) -> str | None:
    if bank is None:
        return None
    texts = [
        q.question_text
        for group in (bank.self_intro_questions, bank.professional_questions, bank.behavior_project_questions)
        for q in group
    ]
    return payload_sha256(texts)


def _public_run(run: dict) -> dict:
    return {key: value for key, value in run.items() if key not in {"input", "output"}}


def _summary(runs: list[dict], review: dict | None, submissions: list[dict]) -> dict:
    by_variant = {}
    for variant in ("baseline", "candidate"):
        selected = [r for r in runs if r["variant"] == variant]
        real = [r for r in selected if r["execution_mode"] == "real"]
        latencies = [r["latency_ms"] for r in selected]
        length_rows = [r["length_diagnostics"] for r in real if r["length_diagnostics"]]
        by_variant[variant] = {
            "runs": len(selected),
            "real": len(real),
            "real_success_rate": len(real) / len(selected) if selected else None,
            "real_by_case": {
                case: sum(r["execution_mode"] == "real" for r in selected if r["case_id"] == case)
                for case in sorted(EXPECTED_CASE_IDS)
            },
            "provider_calls": sum(r["provider_calls"] for r in selected),
            "retry_count": sum(r["retry_count"] for r in selected),
            "latency_ms": {
                "p95": _percentile(latencies, 0.95),
                "max": max(latencies) if latencies else None,
            },
            "failures": {
                field: sum(r[field] == CHECK_FAILED for r in selected)
                for field in (
                    "final_schema_passed", "assembler_passed", "strict_count_passed",
                    "stack_boundary_passed", "duplicate_check_passed",
                )
            },
            "length_diagnostics": _aggregate_lengths(length_rows),
        }
    token = _token_comparison(runs)
    quality = _quality(review, submissions) if review else None
    return {"run_count": len(runs), "variants": by_variant, "token_comparison": token, "quality": quality}


def _aggregate_lengths(rows: list[dict]) -> dict | None:
    if not rows:
        return None
    # Per-run distributions are retained in run records. This roll-up is weighted by question count.
    all_values = [value for row in rows for value in row["overall"]["character_counts"]]
    result = {
        "bank_count": len(rows),
        "question_count": len(all_values),
        "overall": _distribution(all_values),
        "above_module_recommended_total": sum(r["above_module_recommended_total"] for r in rows),
        "by_module": {},
    }
    for module in LENGTH_RANGES:
        module_rows = [r["by_module"][module] for r in rows]
        values = [value for row in module_rows for value in row["character_counts"]]
        low, high = LENGTH_RANGES[module]
        result["by_module"][module] = {
            **_distribution(values),
            "recommended_min": low,
            "recommended_max": high,
            "below_recommended": sum(value < low for value in values),
            "above_recommended": sum(value > high for value in values),
        }
    return result


def _token_comparison(runs: list[dict]) -> dict:
    grouped: dict[tuple[str, int], dict[str, dict]] = {}
    for run in runs:
        grouped.setdefault((run["case_id"], run["pair"]), {})[run["variant"]] = run
    comparable = []
    for key, pair in grouped.items():
        if pair.get("baseline") and pair.get("candidate") and _valid_token_run(pair["baseline"]) and _valid_token_run(pair["candidate"]):
            comparable.append((key, pair["baseline"], pair["candidate"]))
    evaluable = len(comparable) >= MIN_COMPARABLE_PAIRS
    baseline = sum(row[1]["output_tokens"] for row in comparable)
    candidate = sum(row[2]["output_tokens"] for row in comparable)
    reduction = (baseline - candidate) / baseline if evaluable and baseline > 0 else None
    candidate_average = candidate / len(comparable) if evaluable else None
    return {
        "status": "evaluated" if evaluable else "not_evaluable",
        "comparable_pair_count": len(comparable),
        "minimum_comparable_pair_count": MIN_COMPARABLE_PAIRS,
        "baseline_output_tokens": baseline if comparable else None,
        "candidate_output_tokens": candidate if comparable else None,
        "candidate_average_output_tokens": candidate_average,
        "paired_output_token_reduction": reduction,
        "character_length_is_token_substitute": False,
    }


def _quality(review: dict, submissions: list[dict]) -> dict:
    mapping = {row["submission_id"]: row["variant"] for row in submissions}
    result = {}
    for variant in ("baseline", "candidate"):
        selected = [r for r in review["submissions"] if mapping[r["submission_id"]] == variant]
        text_values = [sum(r["text_scores"].values()) / len(TEXT_SCORE_DIMENSIONS) for r in selected]
        metadata_values = [score for r in selected for score in r["metadata_fit_scores"]]
        result[variant] = {
            "submission_count": len(selected),
            "text_quality_mean": _mean(text_values),
            "metadata_fit_mean": _mean(metadata_values),
        }
    result["candidate_minus_baseline_text_quality"] = (
        result["candidate"]["text_quality_mean"] - result["baseline"]["text_quality_mean"]
        if result["candidate"]["text_quality_mean"] is not None and result["baseline"]["text_quality_mean"] is not None else None
    )
    return result


def _thresholds(runs: list[dict], summary: dict, review: dict | None) -> dict:
    candidate = summary["variants"]["candidate"]
    all_failures = sum(
        value for variant in summary["variants"].values() for value in variant["failures"].values()
    )
    token = summary["token_comparison"]
    quality = summary["quality"]
    gates = {
        "pilot_candidate_3_of_3_real": _gate(
            len([r for r in runs if r["variant"] == "candidate" and r["pair"] == 1 and r["execution_mode"] == "real"]) == 3,
            len([r for r in runs if r["variant"] == "candidate" and r["pair"] == 1]) == 3,
        ),
        "candidate_real_success_gte_90pct": _numeric_gate(candidate["real_success_rate"], 0.9, "gte", len(runs) == 30),
        "each_case_candidate_real_gte_4_of_5": _gate(
            all(value >= 4 for value in candidate["real_by_case"].values()), len(runs) == 30
        ),
        "schema_assembler_stack_duplicate_failures_eq_0": _gate(all_failures == 0, len(runs) == 30),
        "comparable_pairs_gte_12": _numeric_gate(token["comparable_pair_count"], MIN_COMPARABLE_PAIRS, "gte", len(runs) == 30),
        "candidate_average_output_tokens_lte_1800": _numeric_gate(token["candidate_average_output_tokens"], OUTPUT_TOKEN_LIMIT, "lte", token["status"] == "evaluated"),
        "paired_output_token_reduction_gte_10pct": _numeric_gate(token["paired_output_token_reduction"], MIN_PAIRED_REDUCTION, "gte", token["status"] == "evaluated"),
        "candidate_p95_lte_90s": _numeric_gate(candidate["latency_ms"]["p95"], 90_000, "lte", len(runs) == 30),
        "candidate_max_lte_120s": _numeric_gate(candidate["latency_ms"]["max"], 120_000, "lte", len(runs) == 30),
        "candidate_text_quality_gte_4": _numeric_gate(quality["candidate"]["text_quality_mean"] if quality else None, 4.0, "gte", quality is not None),
        "text_quality_decline_lte_0_2": _numeric_gate(quality["candidate_minus_baseline_text_quality"] if quality else None, -0.2, "gte", quality is not None),
        "candidate_metadata_v2_fit_gte_3_5": _numeric_gate(quality["candidate"]["metadata_fit_mean"] if quality else None, 3.5, "gte", quality is not None),
    }
    statuses = [item["status"] for item in gates.values()]
    verdict = "pass" if statuses and all(s == "pass" for s in statuses) else "fail" if "fail" in statuses and len(runs) == 30 and review is not None else "pending"
    return {"policy": PROTOCOL_VERSION, "gates": gates, "verdict": verdict, "failure_rule": "any required gate failure rejects v0.2"}


def _gate(passed: bool, evaluable: bool) -> dict:
    return {"status": "pass" if passed and evaluable else "fail" if evaluable else "not_evaluable"}


def _numeric_gate(value, required, operation: str, evaluable: bool) -> dict:
    if not evaluable or value is None:
        status = "not_evaluable"
    else:
        passed = value >= required if operation == "gte" else value <= required
        status = "pass" if passed else "fail"
    return {"status": status, "actual": value, "operator": operation, "required": required}


def _hash_assets(paths: dict[str, Path]) -> dict:
    return {name: {"path": path.relative_to(PROJECT_ROOT).as_posix(), "sha256": _sha256(path)} for name, path in sorted(paths.items())}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _status(value: bool) -> str:
    return CHECK_PASSED if value else CHECK_FAILED


def _score(value: object) -> bool:
    return type(value) is int and 1 <= value <= 5


def _mean(values: list[float | int]) -> float | None:
    return sum(values) / len(values) if values else None


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) * percentile) + 0.999999) - 1))
    return ordered[index]


def _elapsed_ms(started: float) -> int:
    return max(0, int((perf_counter() - started) * 1000))


def _atomic_json(path: Path, payload: dict) -> None:
    _atomic_text(path, json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def _render_markdown(report: dict) -> str:
    token = report["summary"]["token_comparison"]
    lines = [
        "# Phase 2.4D QuestionDraft Prompt Token Experiment",
        "",
        f"- Protocol: `{report['protocol_version']}`",
        f"- Status: `{report['status']}`",
        f"- Completion: `{report['completion_status']}`",
        f"- Runs: {report['summary']['run_count']}/30",
        f"- Comparable pairs: {token['comparable_pair_count']}/{MIN_COMPARABLE_PAIRS} required",
        f"- Token status: `{token['status']}`",
        f"- Threshold verdict: `{report['thresholds']['verdict']}`",
        "- Character length is diagnostic only and never substitutes for Provider output tokens.",
        "- This protocol does not rewrite or reinterpret Phase 2.4B.",
        "- Production default changed: false",
        "",
    ]
    return "\n".join(lines)
