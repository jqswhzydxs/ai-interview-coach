import asyncio
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
import hashlib
import json
import math
import os
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from app.agents.llm_client import LLMClient, LLMRequest, LLMResponse, TokenUsage
from app.agents.question_bank_agent import QuestionBankAgent
from app.agents.question_bank_assembler import (
    _mentioned_technologies,
    normalize_question_text,
)
from app.agents.question_bank_draft_agent import QuestionBankDraftAgent
from app.schemas.question import QuestionBank
from app.schemas.question_draft import QuestionDraftBank
from app.services.provider_failure_observability import (
    TOKEN_FIELDS,
    provider_failure_fields,
    safe_token_usage,
    usage_status,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_CASE_IDS = {
    "backend_go_case",
    "backend_java_case",
    "backend_python_case",
}
TEXT_SCORE_DIMENSIONS = (
    "personalization",
    "technical_correctness_and_stack_boundary",
    "coverage_and_substantive_diversity",
    "interview_training_value",
    "clarity",
)
CHECK_PASSED = "passed"
CHECK_FAILED = "failed"
CHECK_NOT_EVALUATED = "not_evaluated"
CANDIDATE_OUTPUT_TOKEN_LIMIT = 1_800
MIN_COMPARABLE_TOKEN_PAIRS = 3
DEFAULT_ASSET_PATHS = {
    "baseline_agent": PROJECT_ROOT / "app/agents/question_bank_agent.py",
    "candidate_agent": PROJECT_ROOT / "app/agents/question_bank_draft_agent.py",
    "base_agent": PROJECT_ROOT / "app/agents/base.py",
    "baseline_prompt": PROJECT_ROOT
    / "app/agents/prompts/question_bank_agent_v0.1.md",
    "candidate_prompt": PROJECT_ROOT
    / "app/agents/prompts/question_bank_draft_agent_v0.1.md",
    "final_schema": PROJECT_ROOT / "app/schemas/question.py",
    "draft_schema": PROJECT_ROOT / "app/schemas/question_draft.py",
    "assembler": PROJECT_ROOT / "app/agents/question_bank_assembler.py",
}


class QuestionBankABError(RuntimeError):
    pass


class QuestionBankABLockError(QuestionBankABError):
    pass


class QuestionBankABProtocolError(QuestionBankABError):
    pass


class QuestionBankABBudgetError(QuestionBankABError):
    pass


class QuestionBankABAuditError(BaseException):
    """Abort without Agent retry/fallback if the audit cannot be persisted."""


@dataclass(frozen=True)
class QuestionBankABConfig:
    input_path: Path
    run_dir: Path
    max_provider_calls: int = 61
    max_total_tokens: int = 250_000
    execution_deadline_seconds: float = 120.0
    repetitions_per_case: int = 5
    temperature: float = 0.2
    max_attempts: int = 2
    lock_path: Path | None = None

    def __post_init__(self) -> None:
        if self.repetitions_per_case != 5:
            raise ValueError("Phase 2.4B requires exactly five pairs per case")
        if self.max_provider_calls < 1 or self.max_total_tokens < 1:
            raise ValueError("Experiment budgets must be positive")
        if not 0 < self.execution_deadline_seconds <= 120:
            raise ValueError("Execution deadline must be in (0, 120] seconds")
        if self.temperature != 0.2:
            raise ValueError("Phase 2.4B freezes temperature at 0.2")
        if self.max_attempts != 2:
            raise ValueError("Phase 2.4B freezes max attempts at 2")


@dataclass(frozen=True)
class QuestionBankABArtifacts:
    manifest_path: Path
    report_json_path: Path
    report_markdown_path: Path
    question_review_packet_path: Path
    metadata_review_packet_path: Path
    review_template_path: Path
    report: dict


class _BudgetedClient:
    def __init__(self, delegate: LLMClient, runner: "QuestionBankABRunner") -> None:
        self.delegate = delegate
        self.runner = runner
        self.provider = delegate.provider
        self.model_name = delegate.model_name

    async def generate_json(self, request: LLMRequest) -> LLMResponse:
        attempt = self.runner._record_provider_call_started()
        started = perf_counter()
        try:
            response = await self.delegate.generate_json(request)
        except BaseException as exc:
            credential = getattr(self.delegate, "api_key", None)
            sensitive_values = (request.system_prompt, request.user_prompt) + (
                (credential,) if isinstance(credential, str) and credential else ()
            )
            self.runner._record_provider_call_finished(
                attempt,
                usage=getattr(exc, "usage", None),
                response_received=False,
                latency_ms=_elapsed_ms(started),
                failure=provider_failure_fields(exc, sensitive_values=sensitive_values),
                cancelled=isinstance(exc, asyncio.CancelledError),
            )
            raise
        self.runner._record_provider_call_finished(
            attempt,
            usage=response.usage,
            response_received=True,
            latency_ms=_elapsed_ms(started),
        )
        return response


class QuestionBankABRunner:
    """Paired QuestionBank-only A/B runner with persistent safety gates."""

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        config: QuestionBankABConfig,
        asset_paths: dict[str, Path] | None = None,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.config = config
        self.asset_paths = asset_paths or DEFAULT_ASSET_PATHS
        self.now_factory = now_factory or (lambda: datetime.now(timezone.utc))
        self.manifest_path = config.run_dir / "manifest.json"
        self.report_json_path = config.run_dir / "question-bank-ab-report.json"
        self.report_markdown_path = config.run_dir / "question-bank-ab-report.md"
        self.question_review_packet_path = (
            config.run_dir / "blind-question-review-packet.json"
        )
        self.metadata_review_packet_path = (
            config.run_dir / "blind-metadata-review-packet.json"
        )
        self.review_template_path = config.run_dir / "blind-review-template.json"
        self.lock_path = config.lock_path or (
            PROJECT_ROOT / "storage/reports/.question-bank-ab.lock"
        )
        self._manifest: dict | None = None
        self._cases: list[dict] | None = None
        self._budgeted_client = _BudgetedClient(llm_client, self)
        self._provider_context = {"variant": "smoke", "case_id": "provider_smoke", "pair": 0}
        self._provider_attempt = 0

    async def run_smoke(self) -> QuestionBankABArtifacts:
        with self._exclusive_lock("smoke"):
            self._load_or_initialize()
            if self._manifest["completion_status"] == "incomplete":
                raise QuestionBankABProtocolError(
                    "An incomplete experiment requires a new run directory"
                )
            if self._manifest["smoke"]["status"] == "passed":
                return self._artifacts()
            if self._manifest["runs"]:
                raise QuestionBankABProtocolError(
                    "Smoke cannot be rerun after A/B executions exist"
                )
            if not self._execution_guards_hold():
                return self._artifacts()
            if not self._budget_allows_calls(1):
                return self._mark_incomplete("incomplete_budget", "provider_call_budget")

            before = self._budget_snapshot()
            self._set_provider_context("smoke", "provider_smoke", 0)
            started_at = self._iso_now()
            started = perf_counter()
            try:
                async with asyncio.timeout(
                    min(60.0, self.config.execution_deadline_seconds)
                ):
                    response = await self._budgeted_client.generate_json(
                        LLMRequest(
                            system_prompt="Return only one JSON object.",
                            user_prompt='Return {"status":"ok"} with no extra text.',
                            response_schema_name="ProviderSmoke",
                            temperature=0,
                        )
                    )
                passed = isinstance(response.content, dict) and bool(response.content)
                failure_type = None if passed else "schema"
            except TimeoutError:
                passed = False
                failure_type = "deadline"
            except Exception:
                passed = False
                failure_type = "provider"

            usage = self._budget_delta(before)
            self._manifest["smoke"] = {
                "status": "passed" if passed else "failed",
                "started_at": started_at,
                "finished_at": self._iso_now(),
                "latency_ms": _elapsed_ms(started),
                "provider_calls": usage["provider_calls"],
                "token_usage": usage["token_usage"],
                "known_token_usage": usage["known_token_usage"],
                "token_usage_status": usage["token_usage_status"],
                "failure_type": failure_type,
            }
            if passed and usage["unknown_usage_calls"] == 0:
                self._manifest["status"] = "smoke_passed"
                if (
                    self._manifest["budget"]["known_token_usage"]["total_tokens"]
                    > self.config.max_total_tokens
                ):
                    return self._mark_incomplete(
                        "incomplete_budget", "smoke_exceeded_total_token_budget"
                    )
            elif usage["unknown_usage_calls"]:
                return self._mark_incomplete(
                    "incomplete_token_usage", "smoke_token_usage_missing"
                )
            else:
                self._manifest["status"] = "smoke_failed"
                self._manifest["completion_status"] = "incomplete"
                self._manifest["stop_reason"] = f"smoke_{failure_type or 'failed'}"
            self._persist_all()
            return self._artifacts()

    async def run_pilot(self) -> QuestionBankABArtifacts:
        with self._exclusive_lock("pilot"):
            self._load_or_initialize()
            if self._manifest["completion_status"] == "incomplete":
                raise QuestionBankABProtocolError(
                    "An incomplete experiment requires a new run directory"
                )
            if self._manifest["smoke"]["status"] != "passed":
                raise QuestionBankABProtocolError(
                    "Provider smoke must pass before pilot"
                )
            if self._manifest["pilot"]["status"] == "passed":
                return self._artifacts()
            if any(run["pair"] > 1 for run in self._manifest["runs"]):
                raise QuestionBankABProtocolError("Pilot cannot follow full executions")

            self._manifest["status"] = "pilot_running"
            self._manifest["pilot"]["status"] = "running"
            self._persist_all()
            if not await self._run_pairs((1,)):
                return self._artifacts()
            if not self._execution_guards_hold():
                return self._artifacts()

            pilot_runs = [run for run in self._manifest["runs"] if run["pair"] == 1]
            candidate_runs = [
                run for run in pilot_runs if run["variant"] == "candidate"
            ]
            completed_pairs = _pair_completion(pilot_runs)["completed"]
            pilot_passed = len(pilot_runs) == 6 and completed_pairs == 3 and all(
                _candidate_pilot_run_passed(run) for run in candidate_runs
            ) and len(candidate_runs) == 3
            self._manifest["pilot"] = {
                "status": "passed" if pilot_passed else "failed",
                "completed_at": self._iso_now(),
                "run_count": len(pilot_runs),
                "completed_pair_count": completed_pairs,
                "candidate_real_count": sum(
                    run["execution_mode"] == "real" for run in candidate_runs
                ),
                "candidate_gate": {
                    "required": (
                        "3/3 real; no candidate deadline, fallback, schema, or "
                        "assembler failure; no cross-stack or duplicate output"
                    ),
                    "passed": pilot_passed,
                },
                "fallback_count": sum(
                    run["execution_mode"] == "fallback" for run in pilot_runs
                ),
            }
            if pilot_passed:
                self._manifest["status"] = "pilot_passed"
            else:
                self._manifest["status"] = "pilot_failed"
                self._manifest["completion_status"] = "incomplete"
                self._manifest["stop_reason"] = "pilot_quality_or_schema_gate"
            self._persist_all()
            return self._artifacts()

    async def run_full(self) -> QuestionBankABArtifacts:
        with self._exclusive_lock("full"):
            self._load_or_initialize()
            if self._manifest["pilot"]["status"] != "passed":
                raise QuestionBankABProtocolError("Pilot must pass before full A/B")
            if self._manifest["status"] in {"execution_completed", "completed"}:
                return self._artifacts()
            if self._manifest["completion_status"] == "incomplete":
                raise QuestionBankABProtocolError(
                    "An incomplete experiment cannot silently resume"
                )

            self._manifest["status"] = "full_running"
            self._persist_all()
            if not await self._run_pairs(range(2, 6)):
                return self._artifacts()
            if not self._execution_guards_hold():
                return self._artifacts()

            if len(self._manifest["runs"]) != 30:
                return self._mark_incomplete(
                    "incomplete_protocol", "expected_30_ab_executions"
                )
            self._manifest["status"] = "execution_completed"
            self._manifest["completion_status"] = "awaiting_review"
            self._manifest["execution_completed_at"] = self._iso_now()
            self._persist_all()
            return self._artifacts()

    def apply_blind_reviews(self, review_path: Path) -> QuestionBankABArtifacts:
        with self._exclusive_lock("review"):
            self._load_or_initialize()
            if self._manifest["status"] != "execution_completed":
                raise QuestionBankABProtocolError(
                    "Blind reviews require a completed 30-run execution"
                )
            if not self._execution_guards_hold():
                return self._artifacts()
            raw_reviews = json.loads(review_path.read_text(encoding="utf-8"))
            reviews = self._validate_reviews(raw_reviews)
            quality = self._aggregate_reviews(reviews)
            self._manifest["reviews"] = {
                "status": "completed",
                "completed_at": self._iso_now(),
                "submission_count": len(reviews),
                "quality": quality,
            }
            self._manifest["status"] = "completed"
            self._manifest["completion_status"] = "complete"
            self._manifest["completed_at"] = self._iso_now()
            self._persist_all()
            return self._artifacts()

    async def _run_pairs(self, pairs: Iterator[int] | range | tuple[int, ...]) -> bool:
        existing = {
            (run["case_id"], run["pair"], run["variant"])
            for run in self._manifest["runs"]
        }
        for pair in pairs:
            for case in self._cases:
                for execution_order, variant in enumerate(
                    _variant_order(pair), start=1
                ):
                    key = (case["case_id"], pair, variant)
                    if key in existing:
                        continue
                    if not self._execution_guards_hold():
                        return False
                    if not self._budget_allows_execution():
                        self._mark_incomplete(
                            "incomplete_budget", "insufficient_budget_for_full_attempts"
                        )
                        return False

                    record, bank = await self._execute_variant(
                        case=case,
                        pair=pair,
                        variant=variant,
                        execution_order=execution_order,
                    )
                    self._manifest["runs"].append(record)
                    if bank is not None:
                        self._append_review_material(record, bank)
                    self._persist_all()
                    existing.add(key)

                    if self._manifest["budget"]["known_token_usage"]["total_tokens"] > self.config.max_total_tokens:
                        self._mark_incomplete(
                            "incomplete_budget", "total_token_budget_exceeded"
                        )
                        return False
                    if not self._safety_constraints_hold():
                        self._mark_incomplete(
                            "invalidated_safety", "safety_constraint_failed"
                        )
                        return False
        return True

    async def _execute_variant(
        self,
        *,
        case: dict,
        pair: int,
        variant: str,
        execution_order: int,
    ) -> tuple[dict, QuestionBank | None]:
        agent = (
            QuestionBankAgent(
                self._budgeted_client,
                max_real_llm_attempts=self.config.max_attempts,
            )
            if variant == "baseline"
            else QuestionBankDraftAgent(
                self._budgeted_client,
                max_real_llm_attempts=self.config.max_attempts,
            )
        )
        request_schema = QuestionBank if variant == "baseline" else QuestionDraftBank
        request = agent._build_request(case["input"], request_schema)
        if request.temperature != self.config.temperature:
            raise QuestionBankABProtocolError("Agent temperature drift detected")
        if agent.max_real_llm_attempts != self.config.max_attempts:
            raise QuestionBankABProtocolError("Agent retry configuration drift detected")

        before = self._budget_snapshot()
        started_at = self._iso_now()
        started = perf_counter()
        bank: QuestionBank | None = None
        output_received = False
        metadata = None
        terminal_status = "completed"
        runner_failure_types: dict[str, int] = {}
        self._set_provider_context(variant, case["case_id"], pair)
        try:
            async with asyncio.timeout(self.config.execution_deadline_seconds):
                outcome = await agent.execute(case["input"])
                metadata = outcome.metadata
                output_received = True
                try:
                    bank = QuestionBank.model_validate(outcome.output)
                except Exception:
                    terminal_status = "failed"
                    runner_failure_types = {"schema": 1}
        except TimeoutError:
            terminal_status = "deadline"
            runner_failure_types = {"deadline": 1}
        except Exception:
            terminal_status = "failed"
            runner_failure_types = {"runner": 1}

        elapsed_ms = _elapsed_ms(started)
        usage = self._budget_delta(before)
        analysis = _analyze_bank(bank, case["input"]) if bank is not None else None
        failure_types = dict(metadata.failure_counts) if metadata is not None else {}
        failure_types.update(
            {
                key: failure_types.get(key, 0) + value
                for key, value in runner_failure_types.items()
            }
        )
        execution_mode = metadata.execution_mode if metadata is not None else None
        final_schema_status = (
            CHECK_PASSED
            if bank is not None
            else CHECK_FAILED
            if output_received
            else CHECK_NOT_EVALUATED
        )
        assembler_status = _assembler_status(
            variant=variant,
            execution_mode=execution_mode,
            metadata=metadata,
            output_received=output_received,
        )
        record = {
            "sequence": len(self._manifest["runs"]) + 1,
            "variant": variant,
            "case_id": case["case_id"],
            "pair": pair,
            "execution_order": execution_order,
            "actual_order": f"{execution_order}/2",
            "started_at": started_at,
            "finished_at": self._iso_now(),
            "terminal_status": terminal_status,
            "execution_mode": execution_mode,
            "provider_calls": usage["provider_calls"],
            "retry_count": max(0, usage["provider_calls"] - 1),
            "agent_attempt_count": (
                metadata.real_call_count if metadata is not None else None
            ),
            "failure_types": failure_types,
            "latency_ms": elapsed_ms,
            "token_usage": usage["token_usage"],
            "known_token_usage": usage["known_token_usage"],
            "token_usage_status": usage["token_usage_status"],
            "unknown_usage_calls": usage["unknown_usage_calls"],
            "missing_usage_failure_calls": usage["missing_usage_failure_calls"],
            "output_received": output_received,
            "output_token_usage_available": (
                metadata is not None and usage["token_usage"]["output_tokens"] is not None
            ),
            "final_schema_passed": final_schema_status,
            "assembler_passed": assembler_status,
            "strict_count_passed": (
                _check_status(analysis["strict_count_passed"])
                if analysis
                else CHECK_NOT_EVALUATED
            ),
            "stack_boundary_passed": (
                _check_status(analysis["stack_boundary_passed"])
                if analysis
                else CHECK_NOT_EVALUATED
            ),
            "cross_stack_terms": analysis["cross_stack_terms"] if analysis else [],
            "duplicate_check_passed": (
                _check_status(analysis["duplicate_check_passed"])
                if analysis
                else CHECK_NOT_EVALUATED
            ),
            "exact_duplicate_count": (
                analysis["exact_duplicate_count"] if analysis else None
            ),
            "near_duplicate_pair_count": (
                analysis["near_duplicate_pair_count"] if analysis else None
            ),
            "output_fingerprint": _model_fingerprint(bank),
            "submission_id": f"submission-{uuid4().hex[:16]}" if bank else None,
        }
        return record, bank

    def _load_or_initialize(self) -> None:
        self.config.run_dir.mkdir(parents=True, exist_ok=True)
        self._cases = _load_frozen_cases(self.config.input_path)
        input_hash = _sha256_file(self.config.input_path)
        asset_hashes = _hash_assets(self.asset_paths)
        if self.manifest_path.exists():
            try:
                manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                raise QuestionBankABProtocolError(
                    "Experiment manifest is unreadable or damaged"
                ) from exc
            if not isinstance(manifest, dict) or not isinstance(
                manifest.get("runs"), list
            ):
                raise QuestionBankABProtocolError("Experiment manifest is damaged")
            expected_protocol = self._protocol_snapshot()
            if manifest.get("protocol") != expected_protocol:
                raise QuestionBankABProtocolError("Experiment protocol/config drift detected")
            if manifest.get("provider") != self.llm_client.provider:
                raise QuestionBankABProtocolError("Provider drift detected")
            if manifest.get("model") != self.llm_client.model_name:
                raise QuestionBankABProtocolError("Model drift detected")
            if manifest.get("input_sha256") != input_hash:
                raise QuestionBankABProtocolError("Frozen input hash changed")
            self._manifest = manifest
            self._initialize_observability()
            committed = {
                (run["variant"], run["case_id"], run["pair"])
                for run in manifest["runs"]
            }
            interrupted = any(
                item["status"] == "started"
                or (item["variant"] == "smoke" and manifest["smoke"]["status"] == "pending")
                or (
                    item["variant"] != "smoke"
                    and (item["variant"], item["case_id"], item["pair"]) not in committed
                )
                for item in manifest["provider_attempts"]
            )
            if interrupted:
                self._mark_incomplete("incomplete_interrupted", "provider_attempt_or_execution_uncommitted")
            return

        self._manifest = {
            "manifest_version": "phase-2.4b-question-bank-ab-v2",
            "experiment_id": f"qb-ab-{uuid4().hex}",
            "created_at": self._iso_now(),
            "updated_at": self._iso_now(),
            "status": "initialized",
            "completion_status": "pending",
            "stop_reason": None,
            "provider": self.llm_client.provider,
            "model": self.llm_client.model_name,
            "protocol": self._protocol_snapshot(),
            "input_file": self.config.input_path.name,
            "input_sha256": input_hash,
            "case_ids": [case["case_id"] for case in self._cases],
            "asset_hashes": asset_hashes,
            "budget": {
                "max_provider_calls": self.config.max_provider_calls,
                "provider_calls_used": 0,
                "max_total_tokens": self.config.max_total_tokens,
                "input_tokens_used": 0,
                "output_tokens_used": 0,
                "total_tokens_used": 0,
                "unknown_usage_calls": 0,
                "missing_usage_failure_calls": 0,
            },
            "smoke": {"status": "pending"},
            "pilot": {"status": "pending"},
            "runs": [],
            "reviews": {"status": "pending"},
            "safety": {
                "full_upstream_chain_invoked": False,
                "background_tasks_created": False,
                "api_key_logged": False,
                "full_sensitive_inputs_logged": False,
                "raw_provider_responses_logged": False,
                "save_full_llm_logs_required": False,
                "production_default_agent_changed": False,
            },
        }
        self._initialize_observability()
        self._persist_all()

    def _protocol_snapshot(self) -> dict:
        return {
            "variants": {
                "baseline": "QuestionBankAgent/question_bank_agent_v0.1",
                "candidate": "QuestionBankDraftAgent/question_bank_draft_agent_v0.1",
            },
            "pairs_per_case": self.config.repetitions_per_case,
            "pilot_pair": 1,
            "full_continuation_pairs": [2, 3, 4, 5],
            "temperature": self.config.temperature,
            "max_attempts": self.config.max_attempts,
            "execution_deadline_seconds": self.config.execution_deadline_seconds,
            "max_provider_calls": self.config.max_provider_calls,
            "max_total_tokens": self.config.max_total_tokens,
            "candidate_average_output_token_limit": CANDIDATE_OUTPUT_TOKEN_LIMIT,
            "minimum_comparable_token_pairs": MIN_COMPARABLE_TOKEN_PAIRS,
            "order_rule": "odd pair baseline->candidate; even pair candidate->baseline",
            "pair_completion_rule": (
                "completed after both variants finish an attempt, regardless of output"
            ),
            "pilot_gate_rule": "candidate-only",
        }

    def _assert_assets_unchanged(self) -> None:
        current = _hash_assets(self.asset_paths)
        if current != self._manifest["asset_hashes"]:
            raise QuestionBankABProtocolError("Frozen A/B asset hash changed")

    def _safety_constraints_hold(self) -> bool:
        safety = self._manifest.get("safety")
        return isinstance(safety, dict) and safety == {
            "full_upstream_chain_invoked": False,
            "background_tasks_created": False,
            "api_key_logged": False,
            "full_sensitive_inputs_logged": False,
            "raw_provider_responses_logged": False,
            "save_full_llm_logs_required": False,
            "production_default_agent_changed": False,
        }

    def _execution_guards_hold(self) -> bool:
        try:
            self._assert_assets_unchanged()
        except QuestionBankABProtocolError:
            self._mark_incomplete("invalidated_assets", "asset_hash_changed")
            return False
        if not self._safety_constraints_hold():
            self._mark_incomplete("invalidated_safety", "safety_constraint_failed")
            return False
        return True

    def _budget_allows_calls(self, count: int) -> bool:
        budget = self._manifest["budget"]
        return (
            budget["provider_calls_used"] + count <= budget["max_provider_calls"]
            and budget["known_token_usage"]["total_tokens"] < budget["max_total_tokens"]
        )

    def _budget_allows_execution(self) -> bool:
        return self._budget_allows_calls(self.config.max_attempts)

    def _initialize_observability(self) -> None:
        budget = self._manifest["budget"]
        self._manifest.setdefault("provider_observability", {
            "version": "safe-provider-attempts-v1",
            "mode": "report_only",
            "audit_source": "manifest.json",
            "legacy_unobserved_calls": budget["provider_calls_used"],
        })
        self._manifest.setdefault("provider_attempts", [])
        budget.setdefault("known_token_usage", {
            key: budget.get(f"{key}_used") or 0 for key in TOKEN_FIELDS
        })
        legacy_missing = budget["unknown_usage_calls"] + budget["missing_usage_failure_calls"]
        budget.setdefault("missing_token_usage_calls", {
            key: legacy_missing for key in TOKEN_FIELDS
        })
        for run in self._manifest["runs"]:
            if "known_token_usage" not in run:
                run["known_token_usage"] = dict(run["token_usage"])
                if run.get("unknown_usage_calls", 0) or run.get("missing_usage_failure_calls", 0):
                    run["token_usage"] = {key: None for key in TOKEN_FIELDS}
                    run["output_token_usage_available"] = False
                run["token_usage_status"] = usage_status(run["token_usage"])
        self._refresh_budget_usage()

    def _refresh_budget_usage(self) -> None:
        budget = self._manifest["budget"]
        for key in TOKEN_FIELDS:
            budget[f"{key}_used"] = (
                None if budget["missing_token_usage_calls"][key]
                else budget["known_token_usage"][key]
            )
        budget["token_usage_status"] = usage_status({
            key: budget[f"{key}_used"] for key in TOKEN_FIELDS
        }) if budget["provider_calls_used"] else "not_available"

    def _set_provider_context(self, variant: str, case_id: str, pair: int) -> None:
        self._provider_context = {"variant": variant, "case_id": case_id, "pair": pair}
        self._provider_attempt = 0

    def _record_provider_call_started(self) -> dict:
        budget = self._manifest["budget"]
        if budget["provider_calls_used"] >= budget["max_provider_calls"]:
            raise QuestionBankABBudgetError("Provider call budget exhausted")
        budget["provider_calls_used"] += 1
        self._provider_attempt += 1
        record = {
            **self._provider_context,
            "attempt": self._provider_attempt,
            "call_index": budget["provider_calls_used"],
            "status": "started",
            "started_at": self._iso_now(),
            "finished_at": None,
            "failure_category": None,
            "exception_type": None,
            "http_status_code": None,
            "provider_error_code": None,
            "request_id": None,
            "retry_after": None,
            "filtered_fields": [],
            "latency_ms": None,
            "token_usage_available": False,
            "token_usage_status": "not_available",
            "token_usage": {key: None for key in TOKEN_FIELDS},
        }
        self._manifest["provider_attempts"].append(record)
        for key in TOKEN_FIELDS:
            budget["missing_token_usage_calls"][key] += 1
        self._refresh_budget_usage()
        self._persist_provider_audit()
        return record

    def _record_provider_call_finished(
        self,
        record: dict,
        *,
        usage: TokenUsage | None,
        response_received: bool,
        latency_ms: int,
        failure: dict | None = None,
        cancelled: bool = False,
    ) -> None:
        tokens = safe_token_usage(usage)
        record.update({
            "status": "cancelled" if cancelled else "failed" if failure else "completed",
            "finished_at": self._iso_now(),
            "latency_ms": latency_ms,
            "token_usage": tokens,
            "token_usage_available": usage_status(tokens) == "available",
            "token_usage_status": usage_status(tokens),
        })
        if failure is not None:
            record.update(failure)
        budget = self._manifest["budget"]
        if tokens["total_tokens"] is None:
            target = (
                "unknown_usage_calls"
                if response_received
                else "missing_usage_failure_calls"
            )
            budget[target] += 1
        for key, value in tokens.items():
            if value is not None:
                budget["known_token_usage"][key] += value
                budget["missing_token_usage_calls"][key] -= 1
        self._refresh_budget_usage()
        # Synchronous atomic persistence happens before the exception reaches retry/fallback.
        self._persist_provider_audit()

    def _persist_provider_audit(self) -> None:
        try:
            self._persist_all()
        except OSError:
            raise QuestionBankABAuditError("Provider audit persistence failed; experiment aborted") from None

    def _budget_snapshot(self) -> dict:
        return json.loads(json.dumps(self._manifest["budget"]))

    def _budget_delta(self, before: dict) -> dict:
        after = self._manifest["budget"]
        known = {
            key: after["known_token_usage"][key] - before["known_token_usage"][key]
            for key in TOKEN_FIELDS
        }
        tokens = {
            key: None if (
                after["missing_token_usage_calls"][key]
                - before["missing_token_usage_calls"][key]
            ) else known[key]
            for key in TOKEN_FIELDS
        }
        return {
            "provider_calls": after["provider_calls_used"]
            - before["provider_calls_used"],
            "unknown_usage_calls": after["unknown_usage_calls"]
            - before["unknown_usage_calls"],
            "missing_usage_failure_calls": after["missing_usage_failure_calls"]
            - before["missing_usage_failure_calls"],
            "token_usage": tokens,
            "known_token_usage": known,
            "token_usage_status": usage_status(tokens),
        }

    def _append_review_material(self, record: dict, bank: QuestionBank) -> None:
        question_packet = _read_json_or_default(
            self.question_review_packet_path,
            {
                "packet_version": "phase-2.4b-blind-question-v1",
                "blinding": "Variant, pair, and execution order are intentionally omitted.",
                "submissions": [],
            },
        )
        metadata_packet = _read_json_or_default(
            self.metadata_review_packet_path,
            {
                "packet_version": "phase-2.4b-blind-metadata-v1",
                "blinding": "Variant, pair, and execution order are intentionally omitted.",
                "submissions": [],
            },
        )
        all_questions = [
            *bank.self_intro_questions,
            *bank.professional_questions,
            *bank.behavior_project_questions,
        ]
        question_packet["submissions"].append(
            {
                "submission_id": record["submission_id"],
                "case_id": record["case_id"],
                "questions": [
                    {
                        "position": index,
                        "module": question.module,
                        "question_text": question.question_text,
                    }
                    for index, question in enumerate(all_questions, start=1)
                ],
            }
        )
        metadata_packet["submissions"].append(
            {
                "submission_id": record["submission_id"],
                "case_id": record["case_id"],
                "questions": [
                    {
                        "position": index,
                        "module": question.module,
                        "question_text": question.question_text,
                        "purpose": question.purpose,
                        "difficulty": question.difficulty,
                        "source_type": question.source_type,
                        "source_summaries": [
                            source.summary for source in question.source_refs
                        ],
                        "jd_keywords": question.jd_keywords,
                        "answer_framework": question.answer_framework,
                        "star_template": question.star_template,
                        "scoring_anchors": [
                            anchor.model_dump(mode="json")
                            for anchor in question.scoring_anchors
                        ],
                        "follow_up_questions": question.follow_up_questions,
                        "preparation_advice": question.preparation_advice,
                    }
                    for index, question in enumerate(all_questions, start=1)
                ],
            }
        )
        question_packet["submissions"].sort(key=lambda item: item["submission_id"])
        metadata_packet["submissions"].sort(key=lambda item: item["submission_id"])
        _atomic_write_json(self.question_review_packet_path, question_packet)
        _atomic_write_json(self.metadata_review_packet_path, metadata_packet)
        _atomic_write_json(
            self.review_template_path,
            {
                "review_version": "phase-2.4b-blind-review-v1",
                "scale": "1-5",
                "text_score_dimensions": list(TEXT_SCORE_DIMENSIONS),
                "instructions": (
                    "Score question text before consulting metadata. Then provide exactly "
                    "25 metadata-fit scores, one per question position."
                ),
                "submissions": [
                    {
                        "submission_id": item["submission_id"],
                        "text_scores": {
                            dimension: None for dimension in TEXT_SCORE_DIMENSIONS
                        },
                        "metadata_fit_scores": [None] * 25,
                    }
                    for item in question_packet["submissions"]
                ],
            },
        )

    def _validate_reviews(self, payload: dict) -> dict[str, dict]:
        expected_ids = {
            run["submission_id"]
            for run in self._manifest["runs"]
            if run["submission_id"] is not None
        }
        submissions = payload.get("submissions")
        if not isinstance(submissions, list):
            raise QuestionBankABProtocolError("Review submissions must be a list")
        by_id: dict[str, dict] = {}
        for item in submissions:
            if not isinstance(item, dict) or not isinstance(
                item.get("submission_id"), str
            ):
                raise QuestionBankABProtocolError("Review submission id is invalid")
            submission_id = item["submission_id"]
            if submission_id in by_id:
                raise QuestionBankABProtocolError("Duplicate review submission id")
            text_scores = item.get("text_scores")
            if not isinstance(text_scores, dict) or set(text_scores) != set(
                TEXT_SCORE_DIMENSIONS
            ):
                raise QuestionBankABProtocolError("Review text dimensions are incomplete")
            if not all(_valid_score(score) for score in text_scores.values()):
                raise QuestionBankABProtocolError("Text scores must be within 1-5")
            metadata_scores = item.get("metadata_fit_scores")
            if (
                not isinstance(metadata_scores, list)
                or len(metadata_scores) != 25
                or not all(_valid_score(score) for score in metadata_scores)
            ):
                raise QuestionBankABProtocolError(
                    "Each submission requires 25 metadata scores within 1-5"
                )
            by_id[submission_id] = {
                "text_scores": text_scores,
                "metadata_fit_scores": metadata_scores,
            }
        if set(by_id) != expected_ids:
            raise QuestionBankABProtocolError("Review submission set is incomplete")
        return by_id

    def _aggregate_reviews(self, reviews: dict[str, dict]) -> dict:
        result: dict[str, dict] = {}
        for variant in ("baseline", "candidate"):
            variant_runs = [
                run
                for run in self._manifest["runs"]
                if run["variant"] == variant and run["submission_id"] in reviews
            ]
            result[variant] = {
                "real_only": _quality_slice(
                    [run for run in variant_runs if run["execution_mode"] == "real"],
                    reviews,
                ),
                "user_visible": _quality_slice(variant_runs, reviews),
            }
        return result

    def _mark_incomplete(self, status: str, reason: str) -> QuestionBankABArtifacts:
        self._manifest["status"] = status
        self._manifest["completion_status"] = "incomplete"
        self._manifest["stop_reason"] = reason
        self._manifest["stopped_at"] = self._iso_now()
        self._persist_all()
        return self._artifacts()

    def _persist_all(self) -> None:
        self._manifest["updated_at"] = self._iso_now()
        self._write_manifest()
        report = self._build_report()
        _atomic_write_json(self.report_json_path, report)
        _atomic_write_text(self.report_markdown_path, _render_markdown(report))

    def _write_manifest(self) -> None:
        if self._manifest is not None:
            _atomic_write_json(self.manifest_path, self._manifest)

    def _build_report(self) -> dict:
        summary = _operational_summary(self._manifest["runs"])
        quality = self._manifest.get("reviews", {}).get("quality")
        thresholds = _evaluate_thresholds(summary, quality)
        return {
            "report_version": "phase-2.4b-question-bank-ab-v2",
            "experiment_id": self._manifest["experiment_id"],
            "status": self._manifest["status"],
            "completion_status": self._manifest["completion_status"],
            "stop_reason": self._manifest.get("stop_reason"),
            "provider": self._manifest["provider"],
            "model": self._manifest["model"],
            "protocol": self._manifest["protocol"],
            "input_file": self._manifest["input_file"],
            "input_sha256": self._manifest["input_sha256"],
            "asset_hashes": self._manifest["asset_hashes"],
            "budget": self._manifest["budget"],
            "provider_observability": self._manifest["provider_observability"],
            "provider_attempts": self._manifest["provider_attempts"],
            "smoke": self._manifest["smoke"],
            "pilot": self._manifest["pilot"],
            "runs": self._manifest["runs"],
            "summary": summary,
            "quality": quality or {"status": "pending_blind_review"},
            "thresholds": thresholds,
            "safety": self._manifest["safety"],
        }

    def _artifacts(self) -> QuestionBankABArtifacts:
        report = json.loads(self.report_json_path.read_text(encoding="utf-8"))
        return QuestionBankABArtifacts(
            manifest_path=self.manifest_path,
            report_json_path=self.report_json_path,
            report_markdown_path=self.report_markdown_path,
            question_review_packet_path=self.question_review_packet_path,
            metadata_review_packet_path=self.metadata_review_packet_path,
            review_template_path=self.review_template_path,
            report=report,
        )

    @contextmanager
    def _exclusive_lock(self, phase: str) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        token = uuid4().hex
        payload = {
            "token": token,
            "pid": os.getpid(),
            "phase": phase,
            "run_dir": str(self.config.run_dir.resolve()),
            "acquired_at": self._iso_now(),
        }
        try:
            descriptor = os.open(
                self.lock_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            )
        except FileExistsError as exc:
            raise QuestionBankABLockError(
                f"Another QuestionBank A/B process holds {self.lock_path}"
            ) from exc
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            yield
        finally:
            try:
                current = json.loads(self.lock_path.read_text(encoding="utf-8"))
                if current.get("token") == token:
                    self.lock_path.unlink()
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                pass

    def _iso_now(self) -> str:
        return self.now_factory().isoformat()


def _load_frozen_cases(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list) or len(cases) != 3:
        raise QuestionBankABProtocolError("Exactly three frozen cases are required")
    result: list[dict] = []
    for item in cases:
        if not isinstance(item, dict):
            raise QuestionBankABProtocolError("Frozen case must be an object")
        case_id = item.get("case_id")
        input_data = item.get("input")
        if not isinstance(case_id, str) or not isinstance(input_data, dict):
            raise QuestionBankABProtocolError("Frozen case id/input is invalid")
        required = {
            "resume_profile",
            "jd_profile",
            "experience_profiles",
            "match_report",
            "preparation_goal",
        }
        if not required.issubset(input_data):
            raise QuestionBankABProtocolError("Frozen structured input is incomplete")
        if _contains_forbidden_input_key(input_data):
            raise QuestionBankABProtocolError("Frozen input contains raw/sensitive fields")
        result.append({"case_id": case_id, "input": input_data})
    if {item["case_id"] for item in result} != EXPECTED_CASE_IDS:
        raise QuestionBankABProtocolError("Frozen case ids do not match protocol")
    return sorted(result, key=lambda item: item["case_id"])


def _contains_forbidden_input_key(value: Any) -> bool:
    forbidden = {
        "api_key",
        "raw_text",
        "resume_text",
        "jd_text",
        "user_answer",
    }
    if isinstance(value, dict):
        return any(
            str(key).casefold() in forbidden or _contains_forbidden_input_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_input_key(item) for item in value)
    return False


def _hash_assets(paths: dict[str, Path]) -> dict:
    return {
        name: {
            "path": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
            if path.is_relative_to(PROJECT_ROOT)
            else path.name,
            "sha256": _sha256_file(path),
        }
        for name, path in sorted(paths.items())
    }


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _model_fingerprint(bank: QuestionBank | None) -> str | None:
    if bank is None:
        return None
    encoded = json.dumps(
        bank.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _variant_order(pair: int) -> tuple[str, str]:
    return ("baseline", "candidate") if pair % 2 else ("candidate", "baseline")


def _check_status(passed: bool) -> str:
    return CHECK_PASSED if passed else CHECK_FAILED


def _assembler_status(
    *,
    variant: str,
    execution_mode: str | None,
    metadata: Any,
    output_received: bool,
) -> str:
    if variant != "candidate" or metadata is None or not output_received:
        return CHECK_NOT_EVALUATED
    if execution_mode == "real":
        return CHECK_PASSED
    fallback_reason = metadata.fallback_reason or {}
    if (
        fallback_reason.get("stage") == "output_transform"
        or fallback_reason.get("code") == "output_transform_validation_failed"
    ):
        return CHECK_FAILED
    return CHECK_NOT_EVALUATED


def _candidate_pilot_run_passed(run: dict) -> bool:
    return (
        run["terminal_status"] == "completed"
        and run["execution_mode"] == "real"
        and run["failure_types"].get("deadline", 0) == 0
        and run["failure_types"].get("schema", 0) == 0
        and run["final_schema_passed"] == CHECK_PASSED
        and run["assembler_passed"] == CHECK_PASSED
        and run["strict_count_passed"] == CHECK_PASSED
        and run["stack_boundary_passed"] == CHECK_PASSED
        and run["duplicate_check_passed"] == CHECK_PASSED
    )


def _pair_completion(runs: list[dict]) -> dict:
    variants_by_pair: dict[tuple[str, int], set[str]] = {}
    for run in runs:
        key = (run["case_id"], run["pair"])
        variants_by_pair.setdefault(key, set()).add(run["variant"])
    completed = sum(
        variants == {"baseline", "candidate"}
        for variants in variants_by_pair.values()
    )
    return {
        "expected": len(EXPECTED_CASE_IDS) * 5,
        "attempted": len(variants_by_pair),
        "completed": completed,
        "incomplete": len(variants_by_pair) - completed,
        "completion_basis": "both_variants_attempted",
    }


def _analyze_bank(bank: QuestionBank, input_data: dict) -> dict:
    groups = [
        bank.self_intro_questions,
        bank.professional_questions,
        bank.behavior_project_questions,
    ]
    questions = [question for group in groups for question in group]
    normalized = [normalize_question_text(question.question_text) for question in questions]
    counts = Counter(normalized)
    exact_duplicate_count = sum(count - 1 for count in counts.values() if count > 1)
    near_pairs = 0
    for left_index, left in enumerate(normalized):
        for right in normalized[left_index + 1 :]:
            if left != right and SequenceMatcher(None, left, right).ratio() >= 0.94:
                near_pairs += 1

    context = QuestionBankAgent._context(
        object.__new__(QuestionBankAgent), input_data
    )
    allowed = _mentioned_technologies(" ".join(context["technologies"]))
    mentioned = _mentioned_technologies(
        " ".join(question.question_text for question in questions)
    )
    cross_stack = sorted(mentioned - allowed)
    return {
        "strict_count_passed": [len(group) for group in groups] == [8, 8, 9]
        and bank.total_count == 25,
        "stack_boundary_passed": not cross_stack,
        "cross_stack_terms": cross_stack,
        "duplicate_check_passed": exact_duplicate_count == 0 and near_pairs == 0,
        "exact_duplicate_count": exact_duplicate_count,
        "near_duplicate_pair_count": near_pairs,
    }


def _check_summary(runs: list[dict], field: str) -> dict:
    passed = sum(run[field] == CHECK_PASSED for run in runs)
    failed = sum(run[field] == CHECK_FAILED for run in runs)
    not_evaluated = sum(run[field] == CHECK_NOT_EVALUATED for run in runs)
    return {
        "evaluated": passed + failed,
        "pass": passed,
        "fail": failed,
        "not_evaluated": not_evaluated,
    }


def _valid_token_run(run: dict) -> bool:
    if not (
        run["terminal_status"] == "completed"
        and run["execution_mode"] == "real"
        and run["final_schema_passed"] == CHECK_PASSED
        and run["output_token_usage_available"]
        and run["token_usage"]["output_tokens"] is not None
    ):
        return False
    return run["variant"] != "candidate" or run["assembler_passed"] == CHECK_PASSED


def _token_comparison(runs: list[dict]) -> dict:
    grouped: dict[tuple[str, int], dict[str, dict]] = {}
    for run in runs:
        grouped.setdefault((run["case_id"], run["pair"]), {})[
            run["variant"]
        ] = run

    comparable = []
    for (case_id, pair), variants in grouped.items():
        baseline = variants.get("baseline")
        candidate = variants.get("candidate")
        if (
            baseline is not None
            and candidate is not None
            and _valid_token_run(baseline)
            and _valid_token_run(candidate)
        ):
            comparable.append((case_id, pair, baseline, candidate))

    comparable_case_ids = sorted({item[0] for item in comparable})
    baseline_output = sum(
        item[2]["token_usage"]["output_tokens"] for item in comparable
    )
    candidate_output = sum(
        item[3]["token_usage"]["output_tokens"] for item in comparable
    )
    relative_evaluable = (
        len(comparable) >= MIN_COMPARABLE_TOKEN_PAIRS
        and set(comparable_case_ids) == EXPECTED_CASE_IDS
        and baseline_output > 0
    )
    relative_reduction = (
        (baseline_output - candidate_output) / baseline_output
        if relative_evaluable and baseline_output > 0
        else None
    )
    relative_status = (
        "pass"
        if relative_reduction is not None and relative_reduction >= 0.4
        else "fail"
        if relative_reduction is not None
        else "not_evaluable"
    )

    candidate_usage_runs = [
        run
        for run in runs
        if run["variant"] == "candidate" and _valid_token_run(run)
    ]
    candidate_average = _mean(
        [run["token_usage"]["output_tokens"] for run in candidate_usage_runs]
    )
    absolute_status = (
        "pass"
        if candidate_average is not None
        and candidate_average <= CANDIDATE_OUTPUT_TOKEN_LIMIT
        else "fail"
        if candidate_average is not None
        else "not_evaluable"
    )
    baseline_runs = [run for run in runs if run["variant"] == "baseline"]
    baseline_all_deadline_censored = bool(baseline_runs) and all(
        run["terminal_status"] == "deadline" for run in baseline_runs
    )
    alternative_used = (
        relative_status == "not_evaluable"
        and baseline_all_deadline_censored
        and absolute_status != "not_evaluable"
    )
    effective_status = absolute_status if alternative_used else relative_status
    effective_method = (
        "candidate_absolute_average"
        if alternative_used
        else "paired_relative_reduction"
        if relative_status != "not_evaluable"
        else "none"
    )
    return {
        "relative": {
            "status": "evaluated" if relative_evaluable else "not_evaluable",
            "threshold_status": relative_status,
            "comparable_pair_count": len(comparable),
            "minimum_comparable_pair_count": MIN_COMPARABLE_TOKEN_PAIRS,
            "comparable_case_ids": comparable_case_ids,
            "baseline_output_tokens": baseline_output if comparable else None,
            "candidate_output_tokens": candidate_output if comparable else None,
            "candidate_output_token_reduction": relative_reduction,
            "required": "gte 0.4",
        },
        "candidate_absolute": {
            "status": (
                "evaluated" if candidate_average is not None else "not_evaluable"
            ),
            "threshold_status": absolute_status,
            "eligible_run_count": len(candidate_usage_runs),
            "average_output_tokens": candidate_average,
            "required": f"lte {CANDIDATE_OUTPUT_TOKEN_LIMIT}",
        },
        "baseline_all_deadline_censored": baseline_all_deadline_censored,
        "alternative_used": alternative_used,
        "effective_gate": {
            "method": effective_method,
            "status": effective_status,
        },
    }


def _operational_summary(runs: list[dict]) -> dict:
    result: dict[str, Any] = {
        "run_count": len(runs),
        "pair_completion": _pair_completion(runs),
        "variants": {},
    }
    for variant in ("baseline", "candidate"):
        selected = [run for run in runs if run["variant"] == variant]
        latencies = [run["latency_ms"] for run in selected]
        failure_types = Counter(
            failure_type
            for run in selected
            for failure_type, count in run["failure_types"].items()
            for _ in range(count)
        )
        variant_summary = {
            "runs": len(selected),
            "real": sum(run["execution_mode"] == "real" for run in selected),
            "fallback": sum(
                run["execution_mode"] == "fallback" for run in selected
            ),
            "real_success_rate": _rate(
                sum(run["execution_mode"] == "real" for run in selected),
                len(selected),
            ),
            "provider_calls": sum(run["provider_calls"] for run in selected),
            "retry_count": sum(run["retry_count"] for run in selected),
            "failure_types": dict(sorted(failure_types.items())),
            "latency_ms": {
                "average": _mean(latencies),
                "p95": _percentile_nearest_rank(latencies, 0.95),
                "max": max(latencies) if latencies else None,
            },
            **_aggregate_usage(selected),
            "output_token_usage_available_runs": sum(
                run["output_token_usage_available"] for run in selected
            ),
            "cross_stack_run_count": sum(
                run["stack_boundary_passed"] == CHECK_FAILED for run in selected
            ),
            "duplicate_run_count": sum(
                run["duplicate_check_passed"] == CHECK_FAILED for run in selected
            ),
            "content_checks": {
                "final_schema": _check_summary(selected, "final_schema_passed"),
                "assembler": _check_summary(selected, "assembler_passed"),
                "strict_count": _check_summary(selected, "strict_count_passed"),
                "stack_boundary": _check_summary(
                    selected, "stack_boundary_passed"
                ),
                "duplicate": _check_summary(selected, "duplicate_check_passed"),
            },
            "by_case": {},
        }
        for case_id in sorted(EXPECTED_CASE_IDS):
            case_runs = [run for run in selected if run["case_id"] == case_id]
            variant_summary["by_case"][case_id] = {
                "runs": len(case_runs),
                "real": sum(run["execution_mode"] == "real" for run in case_runs),
                "fallback": sum(
                    run["execution_mode"] == "fallback" for run in case_runs
                ),
                "real_success_rate": _rate(
                    sum(run["execution_mode"] == "real" for run in case_runs),
                    len(case_runs),
                ),
            }
        result["variants"][variant] = variant_summary

    result["token_comparison"] = _token_comparison(runs)
    result["candidate_output_token_reduction"] = result["token_comparison"][
        "relative"
    ]["candidate_output_token_reduction"]
    return result


def _aggregate_usage(runs: list[dict]) -> dict:
    tokens = {
        key: sum(run["token_usage"][key] for run in runs)
        if runs and all(run["token_usage"][key] is not None for run in runs) else None
        for key in TOKEN_FIELDS
    }
    return {
        "token_usage": tokens,
        "token_usage_status": usage_status(tokens),
        "known_token_usage": {
            key: sum((run.get("known_token_usage", run["token_usage"]).get(key) or 0) for run in runs)
            for key in TOKEN_FIELDS
        },
    }


def _quality_slice(runs: list[dict], reviews: dict[str, dict]) -> dict:
    if not runs:
        return {
            "submission_count": 0,
            "dimension_averages": {},
            "overall": None,
            "metadata_fit": None,
        }
    dimension_averages = {
        dimension: _mean(
            [reviews[run["submission_id"]]["text_scores"][dimension] for run in runs]
        )
        for dimension in TEXT_SCORE_DIMENSIONS
    }
    return {
        "submission_count": len(runs),
        "dimension_averages": dimension_averages,
        "overall": _mean(list(dimension_averages.values())),
        "metadata_fit": _mean(
            [
                score
                for run in runs
                for score in reviews[run["submission_id"]]["metadata_fit_scores"]
            ]
        ),
    }


def _evaluate_thresholds(summary: dict, quality: dict | None) -> dict:
    candidate = summary["variants"]["candidate"]
    execution_complete = summary["run_count"] == 30
    token_comparison = summary["token_comparison"]

    def operational(value, required, operation):
        if not execution_complete:
            return {
                "status": "pending",
                "observed": value,
                "required": f"{operation} {required}",
            }
        return _threshold(value, required, operation)

    checks = {
        "candidate_real_success_gte_90pct": operational(
            candidate["real_success_rate"], 0.9, "gte"
        ),
        "each_case_real_success_gte_4_of_5": {
            "status": "pass"
            if all(
                values["runs"] == 5 and values["real"] >= 4
                for values in candidate["by_case"].values()
            )
            else "fail"
            if summary["run_count"] == 30
            else "pending",
            "value": {
                case_id: values["real"]
                for case_id, values in candidate["by_case"].items()
            },
            "required": "at least 4/5 per case",
        },
        "cross_stack_runs_eq_0": operational(
            candidate["cross_stack_run_count"], 0, "eq"
        ),
        "duplicate_runs_eq_0": operational(
            candidate["duplicate_run_count"], 0, "eq"
        ),
        "output_token_reduction_gte_40pct": {
            "status": (
                token_comparison["relative"]["threshold_status"]
                if execution_complete
                else "pending"
            ),
            "value": token_comparison["relative"][
                "candidate_output_token_reduction"
            ],
            "required": "gte 0.4",
            "comparable_pair_count": token_comparison["relative"][
                "comparable_pair_count"
            ],
            "gating": (
                execution_complete and not token_comparison["alternative_used"]
            ),
        },
        "candidate_average_output_tokens_lte_1800": {
            "status": (
                token_comparison["candidate_absolute"]["threshold_status"]
                if execution_complete
                else "pending"
            ),
            "value": token_comparison["candidate_absolute"][
                "average_output_tokens"
            ],
            "required": f"lte {CANDIDATE_OUTPUT_TOKEN_LIMIT}",
            "gating": execution_complete and token_comparison["alternative_used"],
        },
        "output_token_efficiency_gate": {
            "status": (
                token_comparison["effective_gate"]["status"]
                if execution_complete
                else "pending"
            ),
            "method": token_comparison["effective_gate"]["method"],
            "alternative_used": token_comparison["alternative_used"],
        },
        "candidate_p95_lte_90s": operational(
            candidate["latency_ms"]["p95"], 90_000, "lte"
        ),
        "candidate_max_lte_120s": operational(
            candidate["latency_ms"]["max"], 120_000, "lte"
        ),
        "user_visible_quality_gte_4": {"status": "pending"},
        "metadata_fit_gte_3_5": {"status": "pending"},
    }
    if quality is not None:
        candidate_quality = quality["candidate"]["user_visible"]
        checks["user_visible_quality_gte_4"] = _threshold(
            candidate_quality["overall"], 4.0, "gte"
        )
        checks["metadata_fit_gte_3_5"] = _threshold(
            candidate_quality["metadata_fit"], 3.5, "gte"
        )
    verdict_check_names = (
        "candidate_real_success_gte_90pct",
        "each_case_real_success_gte_4_of_5",
        "cross_stack_runs_eq_0",
        "duplicate_runs_eq_0",
        "output_token_efficiency_gate",
        "candidate_p95_lte_90s",
        "candidate_max_lte_120s",
        "user_visible_quality_gte_4",
        "metadata_fit_gte_3_5",
    )
    statuses = [checks[name]["status"] for name in verdict_check_names]
    verdict = (
        "passed"
        if statuses and all(status == "pass" for status in statuses)
        else "failed"
        if "fail" in statuses
        else "not_evaluable"
        if "not_evaluable" in statuses and "pending" not in statuses
        else "pending"
    )
    return {"verdict": verdict, "checks": checks}


def _threshold(value: float | int | None, required: float | int, operation: str) -> dict:
    if value is None:
        return {"status": "pending", "value": None, "required": required}
    passed = {
        "gte": value >= required,
        "lte": value <= required,
        "eq": value == required,
    }[operation]
    return {
        "status": "pass" if passed else "fail",
        "value": value,
        "required": f"{operation} {required}",
    }


def _render_markdown(report: dict) -> str:
    summary = report["summary"]
    token_comparison = summary["token_comparison"]
    lines = [
        "# Phase 2.4B QuestionBank Paired A/B Report",
        "",
        f"- Status: {report['status']}",
        f"- Completion: {report['completion_status']}",
        f"- Provider / model: {report['provider']} / {report['model']}",
        f"- Executions: {summary['run_count']} / 30",
        f"- Completed pairs: {summary['pair_completion']['completed']} / 15 "
        "(completion means both variants were attempted)",
        f"- Threshold verdict: {report['thresholds']['verdict']}",
        "- Audit mode: report_only; manifest.json is the audit source of truth; AgentRun database writes are not used.",
        "- Missing token usage is unknown/not_available. known_token_usage is a lower bound, not actual total consumption.",
        "",
        "## Operational summary",
        "",
        "| Variant | Runs | Real | Fallback | Calls | Retries | Output tokens | P95 ms | Max ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for variant in ("baseline", "candidate"):
        values = summary["variants"][variant]
        lines.append(
            f"| {variant} | {values['runs']} | {values['real']} | {values['fallback']} | "
            f"{values['provider_calls']} | {values['retry_count']} | "
            f"{_display_usage(values['token_usage']['output_tokens'])} | "
            f"{values['latency_ms']['p95']} | {values['latency_ms']['max']} |"
        )
    lines.extend(
        [
            "",
            "## Execution failures versus content checks",
            "",
            "`terminal_status` describes whether an execution completed, hit its deadline, "
            "or failed. Content checks are tri-state: `passed`, `failed`, or "
            "`not_evaluated`. A check with no QuestionBank output is not a content failure.",
            "",
            "| Variant | Check | Evaluated | Pass | Fail | Not evaluated |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for variant in ("baseline", "candidate"):
        for check_name, values in summary["variants"][variant][
            "content_checks"
        ].items():
            lines.append(
                f"| {variant} | {check_name} | {values['evaluated']} | "
                f"{values['pass']} | {values['fail']} | "
                f"{values['not_evaluated']} |"
            )
    lines.extend(
        [
            "",
            "## Token comparison",
            "",
            f"- Relative comparison: {token_comparison['relative']['status']} "
            f"({token_comparison['relative']['comparable_pair_count']} comparable pairs)",
            f"- Relative reduction: "
            f"{token_comparison['relative']['candidate_output_token_reduction']}",
            f"- Candidate average output tokens: "
            f"{token_comparison['candidate_absolute']['average_output_tokens']}",
            f"- Effective method: {token_comparison['effective_gate']['method']}",
            f"- Alternative absolute threshold used: "
            f"{token_comparison['alternative_used']}",
            f"- Effective token gate: {token_comparison['effective_gate']['status']}",
            "",
            "## Executions",
            "",
            "| Seq | Case | Pair | Order | Variant | Terminal | Mode | Calls | Retry | Latency ms | Tokens | Schema | Assembler | Stack | Duplicate |",
            "| ---: | --- | ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- |",
        ]
    )
    for run in report["runs"]:
        lines.append(
            f"| {run['sequence']} | {run['case_id']} | {run['pair']} | "
            f"{run['actual_order']} | {run['variant']} | {run['terminal_status']} | "
            f"{run['execution_mode'] or 'not_available'} | "
            f"{run['provider_calls']} | {run['retry_count']} | {run['latency_ms']} | "
            f"{_display_usage(run['token_usage']['total_tokens'])} | {run['final_schema_passed']} | "
            f"{run['assembler_passed']} | {run['stack_boundary_passed']} | "
            f"{run['duplicate_check_passed']} |"
        )
    lines.extend([
        "", "## Provider attempt audit", "",
        "Each attempt is checkpointed before the call and immediately on failure/success, before retry or fallback.",
        "Started entries have an unknown outcome; cancellation does not prove an upstream timeout.", "",
        "| Variant | Case | Pair | Attempt | Status | Category | Exception | HTTP | Provider code | Request ID | Retry-After | ms | Usage |",
        "| --- | --- | ---: | ---: | --- | --- | --- | ---: | --- | --- | --- | ---: | --- |",
    ])
    for attempt in report.get("provider_attempts", []):
        fields = [
            attempt.get(key) for key in (
                "variant", "case_id", "pair", "attempt", "status", "failure_category",
                "exception_type", "http_status_code", "provider_error_code", "request_id",
                "retry_after", "latency_ms", "token_usage_status",
            )
        ]
        lines.append("| " + " | ".join(str(value) if value is not None else "not_available" for value in fields) + " |")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This report excludes API keys, full upstream inputs, and raw provider responses. "
            "Question text and curated metadata are stored only in separate blind-review packets.",
            "",
        ]
    )
    return "\n".join(lines)


def _valid_score(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 1 <= value <= 5


def _display_usage(value: int | None) -> str:
    return str(value) if value is not None else "unknown/not_available"


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _mean(values: list[float | int]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def _percentile_nearest_rank(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _elapsed_ms(started_at: float) -> int:
    return max(0, int((perf_counter() - started_at) * 1000))


def _read_json_or_default(path: Path, default: dict) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _atomic_write_json(path: Path, payload: dict) -> None:
    _atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False),
    )


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)
