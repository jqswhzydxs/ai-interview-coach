"""Readiness-gated Phase 2.4D-F-A non-thinking Prompt protocol v5 runner."""

from __future__ import annotations

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
from typing import Any, Mapping
from uuid import uuid4

from app.agents.deepseek_prompt_recovery_experiment_client import safe_usage_details_record
from app.agents.llm_client import LLMClient, LLMRequest, LLMResponse
from app.agents.question_bank_candidate_agent import payload_sha256
from app.agents.question_bank_metadata_v2 import (
    QuestionBankMetadataAssemblerV2,
    collect_evidence,
)
from app.agents.question_draft_prompt_recovery_experiment import (
    PROMPT_RECOVERY_ASSETS,
    QuestionDraftPromptRecoveryExperimentAgent,
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
from app.services.question_draft_provider_readiness_v5 import (
    DEFAULT_FIXTURE_PATH,
    load_and_validate_readiness_ledger,
    readiness_asset_bundle_sha256,
    readiness_ledger_sha256,
)
from app.services.question_draft_token_experiment import (
    COMMON_ASSETS as V1_COMMON_ASSETS,
    FROZEN_INPUT_SHA256,
    LENGTH_RANGES,
    MIN_COMPARABLE_PAIRS,
    OUTPUT_TOKEN_LIMIT,
    TEXT_SCORE_DIMENSIONS,
    _aggregate_lengths,
    _atomic_json,
    _atomic_text,
    _distribution,
    _gate,
    _mean,
    _numeric_gate,
    _question_text_fingerprint,
    _score,
    _status,
    _variant_order,
)
from app.services.question_draft_prompt_recovery_protocol_v5 import (
    PROTOCOL_VERSION,
    TOTAL_TOKEN_BUDGET_POLICY,
    QuestionDraftPromptRecoveryProtocolV5Error,
    account_execution_v5,
    assess_pair_comparability_v5,
    prompt_recovery_protocol_v5_snapshot,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_PROVIDER = "deepseek"
REQUIRED_MODEL = "deepseek-v4-pro"
THINKING_TYPE = "disabled"
PROMPT_VARIANTS = ("baseline", "candidate")
V5_RUNNER_VERSION = PROTOCOL_VERSION + "-runner-v1"
HISTORICAL_REPORT_DIRS = (
    PROJECT_ROOT / "storage/reports/question-bank-ab-phase-2-4b-v2-20261019-run2",
    PROJECT_ROOT / "storage/reports/question-bank-metadata-phase-2-4c-offline-20261020",
    PROJECT_ROOT / "storage/reports/question-bank-candidate-integration-phase-2-4c-20261021",
    PROJECT_ROOT / "storage/reports/question-bank-token-phase-2-4d-a-offline-20261021",
    PROJECT_ROOT / "storage/reports/question-bank-token-phase-2-4d-b-20261022-run1",
    PROJECT_ROOT / "storage/reports/question-bank-token-phase-2-4d-b-20261022-run2",
    PROJECT_ROOT / "storage/reports/question-bank-token-phase-2-4d-b-20261022-run3",
    PROJECT_ROOT
    / "storage/reports/question-bank-token-phase-2-4d-b-protocol-v2-review-20261022",
    PROJECT_ROOT / "storage/reports/question-bank-token-phase-2-4d-b2-readiness-20261022",
    PROJECT_ROOT / "storage/reports/question-bank-token-phase-2-4d-b2-v2-20261022-ab1",
    PROJECT_ROOT / "storage/reports/question-bank-token-phase-2-4d-c-offline-20261022",
    PROJECT_ROOT / "storage/reports/question-bank-token-phase-2-4d-d-a-offline-20261023",
    PROJECT_ROOT / "storage/reports/question-bank-token-phase-2-4d-d-readiness-20261023",
    PROJECT_ROOT / "storage/reports/question-bank-token-phase-2-4d-d-v3-20261023-ab1",
    PROJECT_ROOT / "storage/reports/question-bank-token-phase-2-4d-d-b-offline-20261023",
    PROJECT_ROOT / "storage/reports/question-bank-token-phase-2-4d-e-a-offline-20261023",
    PROJECT_ROOT / "storage/reports/question-bank-token-phase-2-4d-e-readiness-20261024",
    PROJECT_ROOT / "storage/reports/question-bank-token-phase-2-4d-e-v4-20261024-ab1",
    PROJECT_ROOT / "storage/reports/question-bank-token-phase-2-4d-e-b-offline-20261024",
    PROJECT_ROOT / "storage/reports/question-bank-token-phase-2-4d-f-a-offline-20261024",
)
V5_COMMON_ASSETS = {
    **V1_COMMON_ASSETS,
    "prompt_recovery_protocol_v5": PROJECT_ROOT
    / "app/services/question_draft_prompt_recovery_protocol_v5.py",
    "provider_readiness_v5": PROJECT_ROOT
    / "app/services/question_draft_provider_readiness_v5.py",
    "prompt_recovery_runner_v5": Path(__file__).resolve(),
    "prompt_recovery_agent": PROJECT_ROOT
    / "app/agents/question_draft_prompt_recovery_experiment.py",
    "experiment_provider_client": PROJECT_ROOT
    / "app/agents/deepseek_prompt_recovery_experiment_client.py",
    "usage_detail_parser": PROJECT_ROOT / "app/services/provider_usage_details.py",
}


class QuestionDraftPromptRecoveryExperimentV5Error(RuntimeError):
    pass


class QuestionDraftPromptRecoveryExperimentV5ProtocolError(QuestionDraftPromptRecoveryExperimentV5Error):
    pass


class QuestionDraftPromptRecoveryExperimentV5BudgetError(QuestionDraftPromptRecoveryExperimentV5Error):
    pass


@dataclass(frozen=True)
class QuestionDraftPromptRecoveryExperimentV5Config:
    run_dir: Path
    readiness_ledger_path: Path
    input_path: Path = DEFAULT_FIXTURE_PATH
    repetitions_per_case: int = 5
    execution_deadline_seconds: float = 120.0
    temperature: float = 0.2
    max_attempts: int = 2
    max_provider_calls: int = 62
    lock_path: Path | None = None

    def __post_init__(self) -> None:
        if self.repetitions_per_case != 5:
            raise ValueError("Protocol v5 requires exactly five pairs per case")
        if self.execution_deadline_seconds != 120.0:
            raise ValueError("Protocol v5 freezes the variant deadline at 120 seconds")
        if self.temperature != 0.2:
            raise ValueError("Protocol v5 freezes temperature at 0.2")
        if self.max_attempts != 2:
            raise ValueError("Protocol v5 freezes two Agent attempts")
        if self.max_provider_calls != 62:
            raise ValueError("Protocol v5 freezes the Provider call budget at 62")


@dataclass(frozen=True)
class QuestionDraftPromptRecoveryExperimentV5Artifacts:
    manifest_path: Path
    report_path: Path
    report_markdown_path: Path
    blind_packet_path: Path
    review_template_path: Path
    report: dict[str, Any]


class _V5MeasuredClient:
    def __init__(self, delegate: LLMClient, runner: "QuestionDraftPromptRecoveryExperimentV5Runner"):
        self.delegate = delegate
        self.runner = runner
        self.provider = delegate.provider
        self.model_name = delegate.model_name

    async def generate_json(self, request: LLMRequest) -> LLMResponse:
        if len(self.runner._manifest["provider_calls"]) >= self.runner.config.max_provider_calls:
            raise QuestionDraftPromptRecoveryExperimentV5BudgetError(
                "Provider call budget exhausted before call"
            )
        call = {
            "call": len(self.runner._manifest["provider_calls"]) + 1,
            "attempt": self.runner._provider_context.get("attempt"),
            "variant": self.runner._provider_context.get("variant"),
            "case_id": self.runner._provider_context.get("case_id"),
            "pair": self.runner._provider_context.get("pair"),
            "started_at": self.runner._iso_now(),
            "thinking": {"type": getattr(self.delegate, "thinking_type", None)},
            "reasoning_effort": getattr(self.delegate, "reasoning_effort", None),
            "reasoning_effort_present": getattr(
                self.delegate, "reasoning_effort", None
            )
            in {"high", "low"},
        }
        started = perf_counter()
        try:
            response = await self.delegate.generate_json(request)
        except BaseException as exc:
            usage = safe_token_usage(getattr(exc, "usage", None))
            call.update(
                {
                    "provider_status": "failed",
                    "status": "failed",
                    "latency_ms": _elapsed_ms(started),
                    "token_usage": usage,
                    "token_usage_status": usage_status(usage),
                    "usage_details": safe_usage_details_record(None),
                    **provider_failure_fields(
                        exc,
                        sensitive_values=(request.system_prompt, request.user_prompt),
                    ),
                }
            )
            self.runner._manifest["provider_calls"].append(call)
            self.runner._persist()
            raise
        usage = safe_token_usage(response.usage)
        call.update(
            {
                "provider_status": "succeeded",
                "status": "succeeded",
                "latency_ms": _elapsed_ms(started),
                "token_usage": usage,
                "token_usage_status": usage_status(usage),
                "usage_details": safe_usage_details_record(response),
                "failure_category": None,
                "exception_type": None,
                "http_status_code": None,
                "provider_error_code": None,
                "request_id": None,
                "retry_after": None,
                "filtered_fields": [],
            }
        )
        self.runner._manifest["provider_calls"].append(call)
        self.runner._persist()
        return response


class QuestionDraftPromptRecoveryExperimentV5Runner:
    def __init__(
        self,
        *,
        llm_clients: Mapping[str, LLMClient],
        config: QuestionDraftPromptRecoveryExperimentV5Config,
    ) -> None:
        if set(llm_clients) != set(PROMPT_VARIANTS):
            raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                "Protocol v5 requires explicit baseline and candidate clients"
            )
        baseline_client = llm_clients["baseline"]
        for variant in PROMPT_VARIANTS:
            client = llm_clients[variant]
            if (
                type(client) is not type(baseline_client)
                or client.provider != REQUIRED_PROVIDER
                or client.model_name != REQUIRED_MODEL
                or client.provider != baseline_client.provider
                or client.model_name != baseline_client.model_name
            ):
                raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                    "Protocol v5 Provider/model identity drift detected"
                )
            for attribute in ("base_url", "api_key"):
                if getattr(client, attribute, None) != getattr(
                    baseline_client, attribute, None
                ):
                    raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                        f"Protocol v5 {attribute} drift detected"
                    )
            if getattr(client, "thinking_type", None) != THINKING_TYPE:
                raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                    f"Protocol v5 {variant} thinking.type drift detected"
                )
            if getattr(client, "reasoning_effort", None) is not None:
                raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                    f"Protocol v5 {variant} must not send reasoning_effort"
                )
        self.llm_clients = dict(llm_clients)
        self.llm_client = baseline_client
        self.config = config
        self.manifest_path = config.run_dir / "manifest.json"
        self.report_path = config.run_dir / "question-draft-prompt-recovery-v5-report.json"
        self.report_markdown_path = config.run_dir / "question-draft-prompt-recovery-v5-report.md"
        self.blind_packet_path = config.run_dir / "blind-review/question-review-packet.json"
        self.review_template_path = config.run_dir / "blind-review/question-review-template.json"
        self.audit_path = config.run_dir / "audit/executions.json"
        self.private_map_path = config.run_dir / "audit/private-blinding-map.json"
        self.lock_path = config.lock_path or config.run_dir.parent / ".question-draft-prompt-recovery-v5.lock"
        self._provider_context: dict[str, Any] = {}
        self._assert_paths_are_separate()
        # This validation happens before _load_or_initialize can create run_dir.
        try:
            self._readiness = load_and_validate_readiness_ledger(
                config.readiness_ledger_path,
                provider=baseline_client.provider,
                model=baseline_client.model_name,
                fixture_path=config.input_path,
                require_passed=True,
            )
        except Exception as exc:
            raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                "A matching passed readiness ledger is required before creating an A/B run"
            ) from exc
        self._readiness_sha256 = readiness_ledger_sha256(config.readiness_ledger_path)
        self._measured_clients = {
            variant: _V5MeasuredClient(client, self)
            for variant, client in self.llm_clients.items()
        }
        self._load_or_initialize()

    def prepare(self) -> QuestionDraftPromptRecoveryExperimentV5Artifacts:
        with self._exclusive_lock("prepare"):
            self._assert_assets_unchanged()
            self._persist()
            return self._artifacts()

    async def run_smoke(self) -> QuestionDraftPromptRecoveryExperimentV5Artifacts:
        with self._exclusive_lock("smoke"):
            self._assert_assets_unchanged()
            if self._manifest.get("smoke") is not None:
                return self._artifacts()
            self._require_call_capacity(self.config.max_attempts)
            record, _ = await self._execute_variant(
                case=self._cases[0],
                pair=0,
                variant="candidate",
                execution_order=1,
                stage="smoke",
            )
            self._manifest["smoke"] = _public_run(record)
            self._manifest["smoke_audit"] = record
            passed = _safe_real_run_v5(record) and (
                record["successful_response_usage"]["status"] == "complete"
            )
            self._manifest["status"] = "smoke_passed" if passed else "smoke_failed"
            self._manifest["stop_reason"] = (
                None
                if passed
                else "smoke_successful_response_usage_unknown"
                if record["successful_response_usage"]["status"] != "complete"
                else "smoke_not_real_safe"
            )
            self._persist()
            return self._artifacts()

    async def run_pilot(self) -> QuestionDraftPromptRecoveryExperimentV5Artifacts:
        with self._exclusive_lock("pilot"):
            self._assert_assets_unchanged()
            if self._manifest["status"] not in {
                "smoke_passed",
                "pilot_passed",
                "pilot_failed",
            }:
                raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                    "A passed protocol v5 smoke is required before pilot"
                )
            if self._manifest["status"] in {"pilot_passed", "pilot_failed"}:
                return self._artifacts()
            completed = await self._run_pairs((1,))
            candidate = [
                run
                for run in self._manifest["runs"]
                if run["variant"] == "candidate" and run["pair"] == 1
            ]
            passed = completed and len(candidate) == 3 and all(
                _safe_real_run_v5(run) for run in candidate
            )
            self._manifest["status"] = "pilot_passed" if passed else "pilot_failed"
            self._manifest["stop_reason"] = (
                None
                if passed
                else self._manifest.get("stop_reason")
                or "pilot_candidate_not_3_of_3_real_safe"
            )
            self._persist()
            return self._artifacts()

    async def run_full(self) -> QuestionDraftPromptRecoveryExperimentV5Artifacts:
        with self._exclusive_lock("full"):
            self._assert_assets_unchanged()
            if self._manifest["status"] == "execution_completed":
                return self._artifacts()
            if self._manifest["status"] != "pilot_passed":
                raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                    "A passed protocol v5 pilot is required before full"
                )
            completed = await self._run_pairs(range(2, 6))
            if completed and len(self._manifest["runs"]) == 30:
                self._manifest["status"] = "execution_completed"
                self._manifest["completion_status"] = "awaiting_independent_blind_review"
                self._manifest["stop_reason"] = None
            elif self._manifest["status"] == "pilot_passed":
                self._manifest["status"] = "incomplete_execution"
                self._manifest["stop_reason"] = (
                    self._manifest.get("stop_reason") or "paired_execution_incomplete"
                )
            self._persist()
            return self._artifacts()

    def apply_blind_review(self, review_path: Path) -> QuestionDraftPromptRecoveryExperimentV5Artifacts:
        with self._exclusive_lock("finalize"):
            self._assert_assets_unchanged()
            if self._manifest["status"] not in {"execution_completed", "completed"}:
                raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                    "Full execution must complete before review"
                )
            if self._manifest["status"] == "completed":
                return self._artifacts()
            review = json.loads(review_path.read_text(encoding="utf-8"))
            expected = [row["submission_id"] for row in self._blind_submissions()]
            if len(expected) != 30:
                raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                    "Blind review requires exactly 30 safe real submissions"
                )
            supplied = review.get("submissions")
            if not isinstance(supplied, list) or [
                row.get("submission_id") for row in supplied
            ] != expected:
                raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                    "Blind review IDs or order do not match"
                )
            evaluator = review.get("evaluator")
            if review.get("review_version") != PROTOCOL_VERSION + "-independent-review-v1":
                raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                    "Blind review version does not match"
                )
            if not (
                isinstance(evaluator, dict)
                and evaluator.get("type") in {"AI", "human"}
                and isinstance(evaluator.get("identifier"), str)
                and evaluator["identifier"].strip()
                and evaluator.get("independence_confirmed") is True
            ):
                raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                    "Independent evaluator metadata is incomplete"
                )
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
                    raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                        "Blind review scores are incomplete"
                    )
                validated.append(
                    {
                        "submission_id": row["submission_id"],
                        "text_scores": text_scores,
                        "metadata_fit_scores": metadata_scores,
                    }
                )
            self._manifest["review"] = {
                "review_version": review["review_version"],
                "evaluator": evaluator,
                "submissions": validated,
                "score_counts": {
                    "text_dimension_scores": len(validated)
                    * len(TEXT_SCORE_DIMENSIONS),
                    "metadata_fit_scores": len(validated) * 25,
                },
                "source_sha256": _sha256(review_path),
            }
            self._manifest["status"] = "completed"
            self._manifest["completion_status"] = "complete"
            self._manifest["completed_at"] = self._iso_now()
            self._persist()
            return self._artifacts()

    async def _run_pairs(self, pairs: Iterator[int] | range | tuple[int, ...]) -> bool:
        existing = {
            (run["case_id"], run["pair"], run["variant"])
            for run in self._manifest["runs"]
        }
        for pair in pairs:
            for case in self._cases:
                pair_records = []
                for order, variant in enumerate(_variant_order(pair), 1):
                    key = (case["case_id"], pair, variant)
                    if key in existing:
                        pair_records.append(
                            next(
                                run
                                for run in self._manifest["runs"]
                                if (run["case_id"], run["pair"], run["variant"])
                                == key
                            )
                        )
                        continue
                    if not self._has_call_capacity(self.config.max_attempts):
                        self._manifest["status"] = "incomplete_call_budget"
                        self._manifest["stop_reason"] = "insufficient_provider_call_budget"
                        self._persist()
                        return False
                    record, bank = await self._execute_variant(
                        case=case,
                        pair=pair,
                        variant=variant,
                        execution_order=order,
                        stage="paired",
                    )
                    self._manifest["runs"].append(record)
                    pair_records.append(record)
                    if bank is not None and _safe_real_run_v5(record):
                        self._append_blind_submission(record, bank, case["input"])
                    existing.add(key)
                    self._persist()
                if len(pair_records) == 2 and len(
                    {record["request_invariant_sha256"] for record in pair_records}
                ) != 1:
                    self._manifest["status"] = "invalidated_protocol"
                    self._manifest["stop_reason"] = (
                        "prompt_asset_was_not_the_only_request_variable"
                    )
                    self._persist()
                    return False
        return True

    async def _execute_variant(
        self,
        *,
        case: dict[str, Any],
        pair: int,
        variant: str,
        execution_order: int,
        stage: str,
    ) -> tuple[dict[str, Any], QuestionBank | None]:
        expected_hash = self._manifest["prompt_assets"][variant]["sha256"]
        agent = QuestionDraftPromptRecoveryExperimentAgent(
            self._measured_clients[variant],
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
            raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                "Frozen request parameters drifted"
            )
        payload_builder = getattr(self.llm_clients[variant], "request_payload", None)
        if not callable(payload_builder):
            raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                "Protocol v5 client must expose its exact request payload"
            )
        provider_request = payload_builder(request)
        if (
            not isinstance(provider_request, dict)
            or provider_request.get("thinking") != {"type": THINKING_TYPE}
            or "reasoning_effort" in provider_request
        ):
            raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                "Non-thinking or reasoning_effort request control drifted"
            )
        invariant_request = json.loads(json.dumps(provider_request))
        messages = invariant_request.get("messages")
        if not isinstance(messages, list) or not messages or not isinstance(messages[0], dict):
            raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                "Provider request messages are invalid"
            )
        prompt_asset_text = agent.prompt_asset.path.read_text(encoding="utf-8")
        system_content = messages[0].get("content")
        if not isinstance(system_content, str) or system_content.count(prompt_asset_text) != 1:
            raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                "Frozen Prompt asset is not uniquely embedded in the Provider request"
            )
        messages[0]["content"] = system_content.replace(
            prompt_asset_text,
            "__EXPERIMENT_PROMPT_ASSET__",
        )
        request_invariant = payload_sha256(invariant_request)
        provider_request_sha256 = payload_sha256(provider_request)
        calls_before = len(self._manifest["provider_calls"])
        started_at = self._iso_now()
        started = perf_counter()
        bank: QuestionBank | None = None
        metadata = None
        output_received = False
        terminal_status = "completed"
        runner_failures: Counter[str] = Counter()
        self._provider_context = {
            "variant": variant,
            "case_id": case["case_id"],
            "pair": pair,
        }
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
        traces = list(metadata.call_traces) if metadata is not None else []
        accounting_calls = []
        for index, call in enumerate(calls):
            copied = dict(call)
            copied.pop("call", None)
            copied["attempt"] = index + 1
            if index < len(traces):
                copied["status"] = traces[index].status
                if traces[index].failure_type and not copied.get("failure_category"):
                    copied["failure_category"] = traces[index].failure_type
            elif terminal_status != "completed":
                copied["status"] = "failed"
            accounting_calls.append(copied)

        analysis = _analyze_bank(bank, case["input"]) if bank is not None else None
        evidence_safe = False
        execution_mode = metadata.execution_mode if metadata is not None else None
        if bank is not None and execution_mode == "real":
            try:
                validate_evidence_quotes(bank.model_dump(mode="json"), case["input"])
                evidence_safe = True
            except Exception:
                runner_failures["evidence"] += 1
        assembler_status = (
            CHECK_PASSED
            if execution_mode == "real" and evidence_safe
            else CHECK_FAILED
            if metadata is not None
            and metadata.fallback_reason.get("stage") == "output_transform"
            else CHECK_NOT_EVALUATED
        )
        checks = {
            "final_schema": (
                CHECK_PASSED
                if bank is not None
                else CHECK_FAILED
                if output_received
                else CHECK_NOT_EVALUATED
            ),
            "assembler": assembler_status,
            "strict_count": (
                _status(analysis["strict_count_passed"])
                if analysis
                else CHECK_NOT_EVALUATED
            ),
            "stack_boundary": (
                _status(analysis["stack_boundary_passed"])
                if analysis
                else CHECK_NOT_EVALUATED
            ),
            "duplicate": (
                _status(analysis["duplicate_check_passed"])
                if analysis
                else CHECK_NOT_EVALUATED
            ),
            "evidence_safety": (
                CHECK_PASSED
                if evidence_safe
                else CHECK_FAILED
                if bank is not None and execution_mode == "real"
                else CHECK_NOT_EVALUATED
            ),
        }
        safe_valid = (
            terminal_status == "completed"
            and execution_mode == "real"
            and all(value == CHECK_PASSED for value in checks.values())
        )
        try:
            accounting = account_execution_v5(
                accounting_calls,
                final_execution_mode=execution_mode,
                final_output_safe_valid=safe_valid,
                provider_call_limit=self.config.max_provider_calls,
                terminal_status=terminal_status,
            )
        except QuestionDraftPromptRecoveryProtocolV5Error as exc:
            raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                "Provider attempt accounting violates protocol v5"
            ) from exc
        accounting["provider_call_budget"] = self._call_budget_snapshot()
        failures = Counter(metadata.failure_counts if metadata is not None else {})
        failures.update(runner_failures)
        success_usage = accounting["successful_response_usage"]
        success_details = next(
            (
                call["usage_details"]
                for call in reversed(calls)
                if call.get("status") == "succeeded"
            ),
            safe_usage_details_record(None),
        )
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
            "successful_response_usage": success_usage,
            "successful_response_usage_details": success_details,
            "billing_usage_completeness": accounting[
                "billing_usage_completeness"
            ],
            "known_token_lower_bound": accounting["known_token_lower_bound"],
            "provider_call_budget": accounting["provider_call_budget"],
            "execution_reliability": accounting["execution_reliability"],
            "billing_usage_warning": (
                "BILLING USAGE INCOMPLETE"
                if accounting["billing_usage_completeness"]["status"]
                == "incomplete"
                else None
            ),
            "input_tokens": success_usage["input_tokens"],
            "output_tokens": success_usage["output_tokens"],
            "total_tokens": success_usage["total_tokens"],
            "prompt_version": agent.prompt_version,
            "prompt_sha256": agent.prompt_sha256,
            "thinking": {"type": THINKING_TYPE},
            "reasoning_effort": None,
            "reasoning_effort_present": False,
            "metadata_assembler_version": agent.assembler.version,
            "metadata_v2_applied": execution_mode == "real"
            and assembler_status == CHECK_PASSED,
            "request_invariant_sha256": request_invariant,
            "provider_request_sha256": provider_request_sha256,
            "request_schema": request.response_schema_name,
            "temperature": request.temperature,
            "max_tokens": None,
            "input_sha256": payload_sha256(case["input"]),
            "output_fingerprint": (
                payload_sha256(bank.model_dump(mode="json")) if bank else None
            ),
            "question_text_fingerprint": _question_text_fingerprint(bank),
            "output_received": output_received,
            "content_checks": checks,
            "final_schema_passed": checks["final_schema"],
            "assembler_passed": checks["assembler"],
            "strict_count_passed": checks["strict_count"],
            "stack_boundary_passed": checks["stack_boundary"],
            "cross_stack_terms": analysis["cross_stack_terms"] if analysis else [],
            "duplicate_check_passed": checks["duplicate"],
            "evidence_safety_passed": checks["evidence_safety"],
            "exact_duplicate_count": analysis["exact_duplicate_count"] if analysis else None,
            "near_duplicate_pair_count": (
                analysis["near_duplicate_pair_count"] if analysis else None
            ),
            "length_diagnostics": _length_diagnostics(bank),
            "submission_id": (
                f"submission-{uuid4().hex}"
                if bank is not None and stage == "paired" and safe_valid
                else None
            ),
        }
        return record, bank

    def _append_blind_submission(
        self, record: dict[str, Any], bank: QuestionBank, input_data: dict[str, Any]
    ) -> None:
        self._manifest["submissions"].append(
            {
                "submission_id": record["submission_id"],
                "blind_order": uuid4().hex,
                "variant": record["variant"],
                "case_id": record["case_id"],
                "pair": record["pair"],
                "evidence_context": [
                    {
                        "source_type": item.source_type,
                        "field_path": item.path,
                        "quote": item.value,
                        "kind": item.kind,
                    }
                    for item in collect_evidence(input_data)
                ],
                "questions": _curated_questions(bank.model_dump(mode="json")),
            }
        )

    def _load_or_initialize(self) -> None:
        if _sha256(self.config.input_path) != FROZEN_INPUT_SHA256:
            raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                "Phase 2.4D frozen input hash mismatch"
            )
        self._cases = _load_frozen_cases(self.config.input_path)
        common_assets = _hash_assets(V5_COMMON_ASSETS)
        prompt_assets = {
            variant: {
                "prompt_version": asset.prompt_version,
                "path": asset.relative_path,
                "sha256": asset.sha256,
            }
            for variant, asset in PROMPT_RECOVERY_ASSETS.items()
        }
        readiness = self._readiness_reference()
        if self.manifest_path.exists():
            try:
                manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                    "Protocol v5 manifest is unreadable"
                ) from exc
            expected = {
                "protocol_version": PROTOCOL_VERSION,
                "runner_version": V5_RUNNER_VERSION,
                "provider": self.llm_client.provider,
                "model": self.llm_client.model_name,
                "input_sha256": _sha256(self.config.input_path),
                "common_assets": common_assets,
                "prompt_assets": prompt_assets,
                "protocol": self._protocol_snapshot(),
                "readiness": readiness,
            }
            for key, value in expected.items():
                if manifest.get(key) != value:
                    raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                        f"Protocol v5 manifest {key} drift detected"
                    )
            self._manifest = manifest
            return
        if self.config.run_dir.exists() and any(self.config.run_dir.iterdir()):
            raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                "New protocol v5 run directory must be empty"
            )
        self._manifest = {
            "protocol_version": PROTOCOL_VERSION,
            "runner_version": V5_RUNNER_VERSION,
            "experiment_id": f"phase-2-4d-v5-{uuid4().hex}",
            "created_at": self._iso_now(),
            "status": "prepared_offline",
            "completion_status": "not_started",
            "stop_reason": None,
            "provider": self.llm_client.provider,
            "model": self.llm_client.model_name,
            "input_path": _display_path(self.config.input_path),
            "input_sha256": _sha256(self.config.input_path),
            "common_assets": common_assets,
            "prompt_assets": prompt_assets,
            "protocol": self._protocol_snapshot(),
            "readiness": readiness,
            "historical_protocol_v1": "immutable_not_rewritten",
            "historical_protocol_v2": "immutable_not_reused_or_rewritten",
            "historical_protocol_v3": "immutable_not_reused_or_rewritten",
            "historical_protocol_v4": "immutable_not_reused_or_rewritten",
            "historical_v3_samples_reused": False,
            "historical_v4_samples_reused": False,
            "production_default_changed": False,
            "smoke": None,
            "smoke_audit": None,
            "runs": [],
            "submissions": [],
            "provider_calls": [],
            "review": None,
        }
        self._persist()

    def _protocol_snapshot(self) -> dict[str, Any]:
        return {
            **prompt_recovery_protocol_v5_snapshot(),
            "unique_variable": "prompt_asset",
            "baseline_prompt": "question_bank_draft_agent_v0.2",
            "candidate_prompt": "question_bank_draft_agent_v0.3",
            "baseline_thinking": {"type": THINKING_TYPE},
            "candidate_thinking": {"type": THINKING_TYPE},
            "baseline_reasoning_effort": "absent",
            "candidate_reasoning_effort": "absent",
            "reasoning_effort_absent_in_both_arms": True,
            "metadata_assembler": QuestionBankMetadataAssemblerV2.version,
            "pilot": "3 cases x 2 variants x pair 1",
            "full": "3 cases x 5 pairs x 2 variants = 30 runs including pilot",
            "order": "odd baseline-candidate; even candidate-baseline",
            "temperature": self.config.temperature,
            "max_tokens": None,
            "provider_client_timeout_seconds": 60,
            "json_output": {
                "response_format": {"type": "json_object"},
                "schema": "QuestionDraftBank",
            },
            "max_attempts": self.config.max_attempts,
            "variant_deadline_seconds": self.config.execution_deadline_seconds,
            "max_provider_calls": self.config.max_provider_calls,
            "minimum_comparable_pairs": MIN_COMPARABLE_PAIRS,
            "candidate_average_output_tokens_lte": OUTPUT_TOKEN_LIMIT,
            "paired_output_token_change_reported_without_reduction_gate": True,
            "length_ranges": {key: list(value) for key, value in LENGTH_RANGES.items()},
            "length_is_diagnostic_only": True,
            "question_draft_max_length": 500,
        }

    def _readiness_reference(self) -> dict[str, Any]:
        return {
            "path": _display_path(self.config.readiness_ledger_path),
            "sha256": self._readiness_sha256,
            "status": self._readiness["status"],
            "provider": self._readiness["provider"],
            "model": self._readiness["model"],
            "asset_bundle_sha256": self._readiness["asset_bundle_sha256"],
            "expected_asset_bundle_sha256": readiness_asset_bundle_sha256(
                self.config.input_path
            ),
        }

    def _assert_paths_are_separate(self) -> None:
        target = self.config.run_dir.resolve()
        ledger = self.config.readiness_ledger_path.resolve()
        if ledger.is_relative_to(target):
            raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                "Readiness ledger must be outside the A/B run directory"
            )
        for protected in HISTORICAL_REPORT_DIRS:
            source = protected.resolve()
            if target == source or target.is_relative_to(source) or source.is_relative_to(target):
                raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                    "Run directory overlaps a historical experiment"
                )

    def _assert_assets_unchanged(self) -> None:
        load_and_validate_readiness_ledger(
            self.config.readiness_ledger_path,
            provider=self.llm_client.provider,
            model=self.llm_client.model_name,
            fixture_path=self.config.input_path,
            require_passed=True,
        )
        if readiness_ledger_sha256(self.config.readiness_ledger_path) != self._readiness_sha256:
            raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                "Readiness ledger hash drift detected"
            )
        if self._manifest["common_assets"] != _hash_assets(V5_COMMON_ASSETS):
            raise QuestionDraftPromptRecoveryExperimentV5ProtocolError("Common asset drift detected")
        expected_prompts = {
            variant: {
                "prompt_version": asset.prompt_version,
                "path": asset.relative_path,
                "sha256": asset.sha256,
            }
            for variant, asset in PROMPT_RECOVERY_ASSETS.items()
        }
        if self._manifest["prompt_assets"] != expected_prompts:
            raise QuestionDraftPromptRecoveryExperimentV5ProtocolError("Prompt hash drift detected")
        if _sha256(self.config.input_path) != self._manifest["input_sha256"]:
            raise QuestionDraftPromptRecoveryExperimentV5ProtocolError("Input fixture drift detected")

    def _has_call_capacity(self, requested: int) -> bool:
        return (
            len(self._manifest["provider_calls"]) + requested
            <= self.config.max_provider_calls
        )

    def _require_call_capacity(self, requested: int) -> None:
        if not self._has_call_capacity(requested):
            raise QuestionDraftPromptRecoveryExperimentV5BudgetError(
                "Insufficient Provider call budget"
            )

    def _call_budget_snapshot(self) -> dict[str, Any]:
        used = len(self._manifest["provider_calls"])
        return {
            "limit": self.config.max_provider_calls,
            "used": used,
            "remaining": self.config.max_provider_calls - used,
            "hard_stop": True,
            "exhausted": used == self.config.max_provider_calls,
        }

    def _budget_summary(self) -> dict[str, Any]:
        calls = self._manifest["provider_calls"]
        unknown = [
            call["call"]
            for call in calls
            if usage_status(call.get("token_usage", {})) != "available"
        ]
        lower_bound = {}
        for field in TOKEN_FIELDS:
            observed = [
                call.get("token_usage", {}).get(field)
                for call in calls
                if type(call.get("token_usage", {}).get(field)) is int
                and call["token_usage"][field] >= 0
            ]
            lower_bound[field] = sum(observed) if observed else None
        return {
            "provider_call_budget": self._call_budget_snapshot(),
            "successful_response_usage_scope": "per_execution",
            "billing_usage_completeness": {
                "status": (
                    "not_applicable"
                    if not calls
                    else "complete"
                    if not unknown
                    else "incomplete"
                ),
                "unknown_calls": unknown,
            },
            "known_token_lower_bound": lower_bound,
            "total_token_budget_policy": TOTAL_TOKEN_BUDGET_POLICY,
            "total_token_budget_is_hard_gate": False,
        }

    def _persist(self) -> None:
        self.config.run_dir.mkdir(parents=True, exist_ok=True)
        report = self._build_report()
        _atomic_json(self.manifest_path, self._manifest)
        _atomic_json(self.report_path, report)
        _atomic_text(self.report_markdown_path, _render_markdown(report))
        _atomic_json(
            self.audit_path,
            {
                "protocol_version": PROTOCOL_VERSION,
                "readiness_ledger_sha256": self._readiness_sha256,
                "smoke": self._manifest.get("smoke_audit"),
                "runs": self._manifest["runs"],
                "provider_calls": self._manifest["provider_calls"],
            },
        )
        _atomic_json(
            self.private_map_path,
            {
                "mapping": [
                    {
                        key: row[key]
                        for key in ("submission_id", "variant", "case_id", "pair")
                    }
                    for row in self._manifest["submissions"]
                ]
            },
        )
        _atomic_json(
            self.blind_packet_path,
            {
                "packet_version": PROTOCOL_VERSION + "-blind-packet",
                "submissions": [
                    {
                        key: row[key]
                        for key in ("submission_id", "evidence_context", "questions")
                    }
                    for row in self._blind_submissions()
                ],
            },
        )
        _atomic_json(
            self.review_template_path,
            {
                "review_version": PROTOCOL_VERSION + "-independent-review-v1",
                "evaluator": {
                    "type": None,
                    "identifier": None,
                    "independence_confirmed": None,
                },
                "submissions": [
                    {
                        "submission_id": row["submission_id"],
                        "text_scores": {
                            key: None for key in TEXT_SCORE_DIMENSIONS
                        },
                        "metadata_fit_scores": [None] * 25,
                    }
                    for row in self._blind_submissions()
                ],
            },
        )

    def _blind_submissions(self) -> list[dict[str, Any]]:
        return sorted(self._manifest["submissions"], key=lambda row: row["blind_order"])

    def _build_report(self) -> dict[str, Any]:
        runs = [_public_run(run) for run in self._manifest["runs"]]
        summary = _summary_v5(runs, self._manifest.get("review"), self._manifest["submissions"])
        return {
            "protocol_version": PROTOCOL_VERSION,
            "runner_version": V5_RUNNER_VERSION,
            "experiment_id": self._manifest["experiment_id"],
            "status": self._manifest["status"],
            "completion_status": self._manifest["completion_status"],
            "stop_reason": self._manifest.get("stop_reason"),
            "provider": self._manifest["provider"],
            "model": self._manifest["model"],
            "readiness": self._manifest["readiness"],
            "prompt_assets": self._manifest["prompt_assets"],
            "protocol": self._manifest["protocol"],
            "historical_protocol_v1": "immutable_not_rewritten",
            "historical_protocol_v2": "immutable_not_reused_or_rewritten",
            "historical_protocol_v3": "immutable_not_reused_or_rewritten",
            "historical_v3_samples_reused": False,
            "production_default_changed": False,
            "smoke": self._manifest.get("smoke"),
            "runs": runs,
            "budget": self._budget_summary(),
            "summary": summary,
            "thresholds": _thresholds_v5(runs, summary, self._manifest.get("review")),
            "review": (
                {
                    "evaluator": self._manifest["review"]["evaluator"],
                    "source_sha256": self._manifest["review"]["source_sha256"],
                }
                if self._manifest.get("review")
                else None
            ),
        }

    def _artifacts(self) -> QuestionDraftPromptRecoveryExperimentV5Artifacts:
        return QuestionDraftPromptRecoveryExperimentV5Artifacts(
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
            descriptor = os.open(
                self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY
            )
        except FileExistsError as exc:
            raise QuestionDraftPromptRecoveryExperimentV5ProtocolError(
                "Another protocol v5 process holds the lock"
            ) from exc
        try:
            os.write(descriptor, f"{os.getpid()}:{phase}".encode("ascii"))
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


def _safe_real_run_v5(run: dict[str, Any]) -> bool:
    return (
        run["terminal_status"] == "completed"
        and run["execution_mode"] == "real"
        and run["execution_reliability"]["final_output_safe_valid"] is True
        and run["final_schema_passed"] == CHECK_PASSED
        and run["assembler_passed"] == CHECK_PASSED
        and run["strict_count_passed"] == CHECK_PASSED
        and run["stack_boundary_passed"] == CHECK_PASSED
        and run["duplicate_check_passed"] == CHECK_PASSED
        and run["evidence_safety_passed"] == CHECK_PASSED
    )


def _public_run(run: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in run.items() if key not in {"input", "output"}}


def _summary_v5(
    runs: list[dict[str, Any]], review: dict[str, Any] | None, submissions: list[dict]
) -> dict[str, Any]:
    by_variant = {}
    for variant in ("baseline", "candidate"):
        selected = [run for run in runs if run["variant"] == variant]
        safe_real = [run for run in selected if _safe_real_run_v5(run)]
        latencies = [run["latency_ms"] for run in selected]
        lower_bound = {}
        for field in TOKEN_FIELDS:
            observed = [
                run["known_token_lower_bound"].get(field)
                for run in selected
                if run["known_token_lower_bound"].get(field) is not None
            ]
            lower_bound[field] = sum(observed) if observed else None
        by_variant[variant] = {
            "runs": len(selected),
            "real_safe": len(safe_real),
            "real_success_rate": len(safe_real) / len(selected) if selected else None,
            "real_by_case": {
                case: sum(
                    _safe_real_run_v5(run)
                    for run in selected
                    if run["case_id"] == case
                )
                for case in sorted(EXPECTED_CASE_IDS)
            },
            "provider_calls": sum(run["provider_calls"] for run in selected),
            "retry_count": sum(run["retry_count"] for run in selected),
            "billing_incomplete_runs": sum(
                run["billing_usage_completeness"]["status"] == "incomplete"
                for run in selected
            ),
            "known_token_lower_bound": lower_bound,
            "execution_reliability": {
                key: sum(run["execution_reliability"][key] for run in selected)
                for key in (
                    "timeout_attempts",
                    "network_error_attempts",
                    "other_failed_attempts",
                    "retry_count",
                )
            },
            "latency_ms": {
                "p95": _percentile(latencies, 0.95),
                "max": max(latencies) if latencies else None,
            },
            "failures": {
                field: sum(run[field] == CHECK_FAILED for run in selected)
                for field in (
                    "final_schema_passed",
                    "assembler_passed",
                    "strict_count_passed",
                    "stack_boundary_passed",
                    "duplicate_check_passed",
                    "evidence_safety_passed",
                )
            },
            "length_diagnostics": _aggregate_lengths(
                [
                    run["length_diagnostics"]
                    for run in safe_real
                    if run["length_diagnostics"]
                ]
            ),
        }
    token = _token_comparison_v5(runs)
    quality = _quality_v5(review, submissions) if review else None
    return {
        "run_count": len(runs),
        "variants": by_variant,
        "token_comparison": token,
        "quality": quality,
    }


def _token_comparison_v5(runs: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}
    for run in runs:
        grouped.setdefault((run["case_id"], run["pair"]), {})[
            run["variant"]
        ] = run
    comparable = []
    exclusion_reasons: Counter[str] = Counter()
    for key, pair in grouped.items():
        if "baseline" not in pair or "candidate" not in pair:
            exclusion_reasons["pair_incomplete"] += 1
            continue
        assessment = assess_pair_comparability_v5(pair["baseline"], pair["candidate"])
        if assessment["status"] == "comparable":
            comparable.append((key, assessment))
        else:
            exclusion_reasons.update(assessment["reasons"])
    evaluable = len(comparable) >= MIN_COMPARABLE_PAIRS
    baseline = sum(row[1]["baseline_output_tokens"] for row in comparable)
    candidate = sum(row[1]["candidate_output_tokens"] for row in comparable)
    reduction = (
        (baseline - candidate) / baseline
        if evaluable and baseline > 0
        else None
    )
    change = (
        (candidate - baseline) / baseline
        if evaluable and baseline > 0
        else None
    )
    return {
        "status": "evaluated" if evaluable else "not_evaluable",
        "comparable_pair_count": len(comparable),
        "minimum_comparable_pair_count": MIN_COMPARABLE_PAIRS,
        "excluded_pair_reasons": dict(sorted(exclusion_reasons.items())),
        "baseline_output_tokens": baseline if comparable else None,
        "candidate_output_tokens": candidate if comparable else None,
        "candidate_average_output_tokens": (
            candidate / len(comparable) if evaluable else None
        ),
        "paired_output_token_reduction": reduction,
        "paired_output_token_change": change,
        "paired_output_token_change_is_reporting_only": True,
        "character_length_is_token_substitute": False,
    }


def _quality_v5(review: dict, submissions: list[dict]) -> dict[str, Any]:
    mapping = {row["submission_id"]: row["variant"] for row in submissions}
    result: dict[str, Any] = {}
    for variant in PROMPT_VARIANTS:
        selected = [
            row
            for row in review["submissions"]
            if mapping[row["submission_id"]] == variant
        ]
        text_values = [
            sum(row["text_scores"].values()) / len(TEXT_SCORE_DIMENSIONS)
            for row in selected
        ]
        dimension_means = {
            dimension: _mean(
                [row["text_scores"][dimension] for row in selected]
            )
            for dimension in TEXT_SCORE_DIMENSIONS
        }
        metadata_values = [
            score for row in selected for score in row["metadata_fit_scores"]
        ]
        result[variant] = {
            "submission_count": len(selected),
            "text_quality_mean": _mean(text_values),
            "text_dimension_means": dimension_means,
            "metadata_fit_mean": _mean(metadata_values),
        }
    baseline_mean = result["baseline"]["text_quality_mean"]
    candidate_mean = result["candidate"]["text_quality_mean"]
    result["candidate_minus_baseline_text_quality"] = (
        candidate_mean - baseline_mean
        if candidate_mean is not None and baseline_mean is not None
        else None
    )
    return result


def _thresholds_v5(
    runs: list[dict[str, Any]], summary: dict[str, Any], review: dict | None
) -> dict[str, Any]:
    candidate = summary["variants"]["candidate"]
    all_failures = sum(
        value
        for variant in summary["variants"].values()
        for value in variant["failures"].values()
    )
    token = summary["token_comparison"]
    quality = summary["quality"]
    candidate_runs = [run for run in runs if run["variant"] == "candidate"]
    fallback_count = sum(
        run["execution_reliability"]["fallback_used"] is True for run in runs
    )
    request_mismatch_count = sum(
        len(
            {
                run["request_invariant_sha256"]
                for run in runs
                if run["case_id"] == case_id and run["pair"] == pair
            }
        )
        != 1
        for case_id in EXPECTED_CASE_IDS
        for pair in range(1, 6)
        if any(
            run["case_id"] == case_id and run["pair"] == pair for run in runs
        )
    )
    gates = {
        "pilot_candidate_3_of_3_real": _gate(
            len(
                [
                    run
                    for run in runs
                    if run["variant"] == "candidate"
                    and run["pair"] == 1
                    and _safe_real_run_v5(run)
                ]
            )
            == 3,
            len(
                [
                    run
                    for run in runs
                    if run["variant"] == "candidate" and run["pair"] == 1
                ]
            )
            == 3,
        ),
        "candidate_15_of_15_real_safe": _gate(
            len(candidate_runs) == 15
            and all(_safe_real_run_v5(run) for run in candidate_runs),
            len(runs) == 30,
        ),
        "each_case_candidate_5_of_5_real_safe": _gate(
            all(value == 5 for value in candidate["real_by_case"].values()),
            len(runs) == 30,
        ),
        "fallback_count_eq_0": _gate(fallback_count == 0, len(runs) == 30),
        "request_invariant_mismatch_eq_0": _gate(
            request_mismatch_count == 0, len(runs) == 30
        ),
        "schema_assembler_stack_duplicate_evidence_failures_eq_0": _gate(
            all_failures == 0, len(runs) == 30
        ),
        "comparable_pairs_gte_12": _numeric_gate(
            token["comparable_pair_count"],
            MIN_COMPARABLE_PAIRS,
            "gte",
            len(runs) == 30,
        ),
        "candidate_average_output_tokens_lte_1800": _numeric_gate(
            token["candidate_average_output_tokens"],
            OUTPUT_TOKEN_LIMIT,
            "lte",
            token["status"] == "evaluated",
        ),
        "candidate_p95_lte_90s": _numeric_gate(
            candidate["latency_ms"]["p95"], 90_000, "lte", len(runs) == 30
        ),
        "candidate_max_lte_120s": _numeric_gate(
            candidate["latency_ms"]["max"], 120_000, "lte", len(runs) == 30
        ),
        "candidate_text_quality_gte_4": _numeric_gate(
            quality["candidate"]["text_quality_mean"] if quality else None,
            4.0,
            "gte",
            quality is not None,
        ),
        "candidate_text_quality_improvement_gte_0_2": _numeric_gate(
            quality["candidate_minus_baseline_text_quality"] if quality else None,
            0.2,
            "gte",
            quality is not None,
        ),
        **{
            f"candidate_{dimension}_gte_4": _numeric_gate(
                quality["candidate"]["text_dimension_means"][dimension]
                if quality
                else None,
                4.0,
                "gte",
                quality is not None,
            )
            for dimension in TEXT_SCORE_DIMENSIONS
        },
        "candidate_metadata_v2_fit_gte_3_5": _numeric_gate(
            quality["candidate"]["metadata_fit_mean"] if quality else None,
            3.5,
            "gte",
            quality is not None,
        ),
        "independent_blind_review_complete": _gate(
            review is not None and quality is not None,
            len(runs) == 30,
        ),
    }
    statuses = [gate["status"] for gate in gates.values()]
    verdict = (
        "pass"
        if statuses and all(status == "pass" for status in statuses)
        else "fail"
        if "fail" in statuses and len(runs) == 30 and review is not None
        else "pending"
    )
    return {
        "policy": PROTOCOL_VERSION,
        "gates": gates,
        "verdict": verdict,
        "failure_rule": "any required gate failure rejects the Prompt v0.3 candidate",
    }


def _length_diagnostics(bank: QuestionBank | None) -> dict[str, Any] | None:
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
        values = [len(question.question_text) for question in questions]
        all_values.extend(values)
        low, high = LENGTH_RANGES[module]
        result["by_module"][module] = {
            **_distribution(values),
            "character_counts": values,
            "recommended_min": low,
            "recommended_max": high,
            "below_recommended": sum(value < low for value in values),
            "above_recommended": sum(value > high for value in values),
        }
    result["overall"] = {
        **_distribution(all_values),
        "character_counts": all_values,
    }
    result["above_module_recommended_total"] = sum(
        row["above_recommended"] for row in result["by_module"].values()
    )
    return result


def _hash_assets(paths: dict[str, Path]) -> dict[str, dict[str, str]]:
    return {
        name: {"path": _display_path(path), "sha256": _sha256(path)}
        for name, path in sorted(paths.items())
    }


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(
        0,
        min(len(ordered) - 1, int((len(ordered) * percentile) + 0.999999) - 1),
    )
    return ordered[index]


def _elapsed_ms(started: float) -> int:
    return max(0, int((perf_counter() - started) * 1000))


def _render_markdown(report: dict[str, Any]) -> str:
    token = report["summary"]["token_comparison"]
    billing = report["budget"]["billing_usage_completeness"]
    return "\n".join(
        [
            "# Phase 2.4D-F-A Non-thinking Prompt Recovery Experiment v5",
            "",
            f"- Protocol: `{report['protocol_version']}`",
            f"- Status: `{report['status']}`",
            f"- Readiness ledger SHA-256: `{report['readiness']['sha256']}`",
            f"- Runs: {report['summary']['run_count']}/30",
            f"- Comparable pairs: {token['comparable_pair_count']}/{MIN_COMPARABLE_PAIRS}",
            f"- Token status: `{token['status']}`",
            f"- Billing usage completeness: `{billing['status']}`",
            f"- Threshold verdict: `{report['thresholds']['verdict']}`",
            "- Known tokens are a lower-bound audit when billing usage is incomplete.",
            "- Fallback outputs are excluded from Token and quality comparison.",
            "- Paired output-token change is descriptive and has no relative-reduction gate.",
            "- Historical protocols v1/v2/v3/v4 and their samples are not reused or rewritten.",
            "- Production default changed: false",
            "",
        ]
    )
