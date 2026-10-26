"""Phase 2.4D-F-A non-thinking Prompt-recovery accounting protocol v5.

This module is deliberately independent from the v1/v2/v3 experiment runners.  It has
no Provider client dependency and performs no network I/O.  A future real-run
entry point must pass every Provider attempt through these accounting rules and
must pass the readiness gate before it creates an A/B run directory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence


PROTOCOL_VERSION = "phase-2.4d-question-draft-non-thinking-prompt-v5"
TOKEN_FIELDS = ("input_tokens", "output_tokens", "total_tokens")
READINESS_MAX_ATTEMPTS = 2
READINESS_CALLS_PER_ATTEMPT = 1
TOTAL_TOKEN_BUDGET_POLICY = "known_lower_bound_audit"
PER_REQUEST_MAX_TOKENS: None = None


class QuestionDraftPromptRecoveryProtocolV5Error(RuntimeError):
    """The v5 accounting or readiness contract was violated."""


def prompt_recovery_protocol_v5_snapshot() -> dict[str, Any]:
    """Return the choices that must be frozen before any new real data exists."""

    return {
        "protocol_version": PROTOCOL_VERSION,
        "unique_variable": "prompt_asset",
        "baseline": {
            "prompt": "question_bank_draft_agent_v0.2",
            "thinking": {"type": "disabled"},
        },
        "candidate": {
            "prompt": "question_bank_draft_agent_v0.3",
            "thinking": {"type": "disabled"},
        },
        "reasoning_effort": "absent_in_both_arms",
        "thinking_is_explicit_and_fixed": {"type": "disabled"},
        "request_pair_invariant": (
            "all request fields are byte-equivalent after replacing only the frozen Prompt asset"
        ),
        "historical_samples_reused": False,
        "historical_v3_samples_reused": False,
        "historical_v4_samples_reused": False,
        "successful_response_usage": (
            "usage from the final successful real Provider response only"
        ),
        "billing_usage_completeness": (
            "complete only when every Provider attempt has complete usage"
        ),
        "known_token_lower_bound": (
            "sum only observed token fields; an entirely unknown field remains null"
        ),
        "provider_call_budget": "hard_stop_before_the_next_provider_call",
        "execution_reliability": (
            "timeout, network, retry, deadline, real, and fallback are separate"
        ),
        "pair_comparability": (
            "both final outputs real and safe-valid with complete successful-response usage"
        ),
        "failed_attempt_usage": "unknown_is_null_never_zero",
        "billing_incomplete_reporting": "prominent",
        "total_token_budget_policy": TOTAL_TOKEN_BUDGET_POLICY,
        "total_token_budget_is_hard_gate": False,
        "per_request_max_tokens": PER_REQUEST_MAX_TOKENS,
        "max_tokens_change_rule": (
            "any future max_tokens value creates a new fixed protocol and requires a full rerun"
        ),
        "readiness": {
            "separate_from_ab": True,
            "outputs_count_toward_ab": False,
            "max_attempts": READINESS_MAX_ATTEMPTS,
            "provider_calls_per_attempt": READINESS_CALLS_PER_ATTEMPT,
            "retry_inside_attempt": False,
            "pass_condition": (
                "one single-call real safe-valid response with complete successful-response "
                "usage and complete billing usage"
            ),
            "failure_directory_policy": (
                "reuse one readiness ledger; never create A/B run directories until passed"
            ),
        },
    }


def preregistration_v5_snapshot() -> dict[str, Any]:
    """Return the complete machine-readable rules frozen before real execution."""

    return {
        "record_type": "phase_2_4d_f_a_protocol_v5_preregistration",
        "protocol_version": PROTOCOL_VERSION,
        "status": "frozen_offline_before_real_data",
        "protocol": prompt_recovery_protocol_v5_snapshot(),
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "design": {
            "cases": 3,
            "pairs_per_case": 5,
            "paired_samples": 15,
            "pilot_pairs": [1],
            "full_additional_pairs": [2, 3, 4, 5],
            "odd_pair_order": ["baseline", "candidate"],
            "even_pair_order": ["candidate", "baseline"],
            "automatic_stage_chaining": False,
            "historical_samples_reused": False,
            "historical_v3_samples_reused": False,
            "historical_v4_samples_reused": False,
        },
        "frozen_generation": {
            "baseline_prompt_version": "question_bank_draft_agent_v0.2",
            "candidate_prompt_version": "question_bank_draft_agent_v0.3",
            "thinking": {"type": "disabled"},
            "reasoning_effort": "absent",
            "request_schema": "QuestionDraftBank",
            "metadata_assembler": "question_bank_metadata_assembler_v2",
            "temperature": 0.2,
            "max_tokens": None,
            "client_timeout_seconds": 60,
            "execution_deadline_seconds": 120,
            "max_attempts_per_execution": 2,
            "provider_call_budget": 62,
            "response_format": {"type": "json_object"},
        },
        "readiness": {
            "separate_ledger": True,
            "required_before_ab_directory_creation": True,
            "fixture_case_id": "backend_go_case",
            "prompt_version": "question_bank_draft_agent_v0.3",
            "thinking": {"type": "disabled"},
            "reasoning_effort": "absent",
            "max_attempts": 2,
            "provider_calls_per_attempt": 1,
            "internal_retry": False,
            "fallback": False,
            "terminal_reexecution_idempotent": True,
            "dual_authorization": [
                "RUN_REAL_LLM_ACCEPTANCE=true",
                "--authorize-phase-2-4d-f-a-readiness",
            ],
        },
        "stage_authorization_flags": {
            "smoke": "--authorize-phase-2-4d-f-a-smoke",
            "pilot": "--authorize-phase-2-4d-f-a-pilot",
            "full": "--authorize-phase-2-4d-f-a-full",
        },
        "token_accounting": {
            "successful_response_usage": True,
            "billing_usage_completeness": True,
            "known_token_lower_bound": True,
            "provider_call_budget": True,
            "execution_reliability": True,
            "unknown_is_zero": False,
            "usage_detail_whitelist": [
                "reasoning_tokens",
                "visible_completion_tokens",
                "cached_input_tokens",
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
            ],
            "missing_detail_policy": "unknown_never_derived",
            "fallback_comparable": False,
        },
        "blind_review": {
            "submission_count": 30,
            "text_dimensions_per_submission": 5,
            "text_score_count": 150,
            "metadata_scores_per_submission": 25,
            "metadata_score_count": 750,
            "randomized_submission_order": True,
            "private_blinding_map": True,
            "evaluator_metadata_required": [
                "type",
                "identifier",
                "independence_confirmed",
            ],
        },
        "required_final_gates": {
            "candidate_real_safe": "15/15",
            "each_case_candidate_real_safe": "5/5",
            "fallback_count": 0,
            "request_invariant_mismatch_count": 0,
            "schema_assembler_count_stack_duplicate_evidence_failures": 0,
            "minimum_comparable_pairs": 12,
            "candidate_average_output_tokens_lte": 1800,
            "paired_output_token_change_reported": True,
            "candidate_p95_latency_ms_lte": 90_000,
            "candidate_max_latency_ms_lte": 120_000,
            "independent_blind_review_complete": True,
            "candidate_text_quality_gte": 4.0,
            "candidate_minus_baseline_text_quality_gte": 0.2,
            "candidate_personalization_gte": 4.0,
            "candidate_coverage_and_substantive_diversity_gte": 4.0,
            "candidate_interview_training_value_gte": 4.0,
            "candidate_technical_correctness_and_stack_boundary_gte": 4.0,
            "candidate_clarity_gte": 4.0,
            "candidate_metadata_v2_fit_gte": 3.5,
        },
        "failure_rule": "any required gate failure rejects the Prompt v0.3 candidate",
        "privacy": {
            "persist_reasoning_content": False,
            "persist_chain_of_thought": False,
            "persist_raw_provider_response": False,
            "persist_full_sensitive_input_in_reports": False,
            "failed_attempts_are_sanitized_before_persistence": True,
        },
        "production_default_changed": False,
        "quality_thresholds_relaxed": False,
        "prompt_v0_3_created": True,
    }


def _token_value(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _attempt_usage(attempt: Mapping[str, Any]) -> dict[str, int | None]:
    raw = attempt.get("token_usage")
    usage = raw if isinstance(raw, Mapping) else {}
    return {field: _token_value(usage.get(field)) for field in TOKEN_FIELDS}


def _usage_is_complete(usage: Mapping[str, int | None]) -> bool:
    return all(_token_value(usage.get(field)) is not None for field in TOKEN_FIELDS)


def _attempt_number(attempt: Mapping[str, Any], fallback: int) -> int:
    value = attempt.get("call", attempt.get("attempt"))
    return value if type(value) is int and value >= 1 else fallback


def _failure_kind(attempt: Mapping[str, Any]) -> str:
    category = attempt.get("failure_category")
    exception_type = attempt.get("exception_type")
    failure_type = attempt.get("failure_type")
    if category in {"read_timeout", "connect_timeout"} or failure_type == "timeout":
        return "timeout"
    if category == "network" or exception_type == "RemoteProtocolError":
        return "network"
    return "other"


def account_execution_v5(
    attempts: Sequence[Mapping[str, Any]],
    *,
    final_execution_mode: str | None,
    final_output_safe_valid: bool,
    provider_call_limit: int,
    terminal_status: str | None = "completed",
) -> dict[str, Any]:
    """Account for one execution without merging failed and successful usage.

    ``known_token_lower_bound`` keeps a field as ``None`` when no attempt exposed
    any value for that field.  This prevents an unknown failed attempt from being
    serialized as a measured zero.
    """

    if type(provider_call_limit) is not int or provider_call_limit < 1:
        raise QuestionDraftPromptRecoveryProtocolV5Error(
            "provider_call_limit must be a positive integer"
        )
    if len(attempts) > provider_call_limit:
        raise QuestionDraftPromptRecoveryProtocolV5Error("Provider call budget was exceeded")
    if final_execution_mode not in {None, "real", "fallback", "mock"}:
        raise QuestionDraftPromptRecoveryProtocolV5Error("Unsupported final execution mode")
    if type(final_output_safe_valid) is not bool:
        raise QuestionDraftPromptRecoveryProtocolV5Error(
            "final_output_safe_valid must be explicit"
        )

    normalized: list[dict[str, Any]] = []
    for index, attempt in enumerate(attempts, start=1):
        status = attempt.get("status")
        if status not in {"succeeded", "failed"}:
            raise QuestionDraftPromptRecoveryProtocolV5Error("Attempt status must be explicit")
        normalized.append(
            {
                "attempt": _attempt_number(attempt, index),
                "status": status,
                "usage": _attempt_usage(attempt),
                "failure_kind": _failure_kind(attempt) if status == "failed" else None,
            }
        )

    successful = [attempt for attempt in normalized if attempt["status"] == "succeeded"]
    if len(successful) > 1:
        raise QuestionDraftPromptRecoveryProtocolV5Error(
            "An execution cannot contain multiple successful Provider responses"
        )
    if final_execution_mode == "real" and len(successful) != 1:
        raise QuestionDraftPromptRecoveryProtocolV5Error(
            "A real final output requires exactly one successful Provider response"
        )
    if final_execution_mode != "real" and successful:
        raise QuestionDraftPromptRecoveryProtocolV5Error(
            "A successful Provider response cannot end as a non-real output"
        )

    if successful:
        final_success = successful[0]
        success_complete = _usage_is_complete(final_success["usage"])
        successful_response_usage: dict[str, Any] = {
            "status": "complete" if success_complete else "unknown",
            "attempt": final_success["attempt"],
            **final_success["usage"],
        }
    else:
        successful_response_usage = {
            "status": "not_applicable",
            "attempt": None,
            **{field: None for field in TOKEN_FIELDS},
        }

    unknown_usage_attempts = [
        attempt["attempt"]
        for attempt in normalized
        if not _usage_is_complete(attempt["usage"])
    ]
    if not normalized:
        billing_status = "not_applicable"
        billing_complete: bool | None = None
    else:
        billing_complete = not unknown_usage_attempts
        billing_status = "complete" if billing_complete else "incomplete"

    lower_bound: dict[str, int | None] = {}
    for field in TOKEN_FIELDS:
        observed = [
            attempt["usage"][field]
            for attempt in normalized
            if attempt["usage"][field] is not None
        ]
        lower_bound[field] = sum(observed) if observed else None

    failed = [attempt for attempt in normalized if attempt["status"] == "failed"]
    failure_counts = {
        kind: sum(attempt["failure_kind"] == kind for attempt in failed)
        for kind in ("timeout", "network", "other")
    }
    reliability = {
        "terminal_status": terminal_status,
        "final_execution_mode": final_execution_mode,
        "final_output_real": final_execution_mode == "real",
        "final_output_safe_valid": final_output_safe_valid,
        "provider_calls": len(normalized),
        "successful_attempts": len(successful),
        "failed_attempts": len(failed),
        "timeout_attempts": failure_counts["timeout"],
        "network_error_attempts": failure_counts["network"],
        "other_failed_attempts": failure_counts["other"],
        "retry_count": max(0, len(normalized) - 1),
        "fallback_used": final_execution_mode == "fallback",
        "deadline_terminated": terminal_status == "deadline",
    }
    return {
        "protocol_version": PROTOCOL_VERSION,
        "successful_response_usage": successful_response_usage,
        "billing_usage_completeness": {
            "status": billing_status,
            "is_complete": billing_complete,
            "unknown_attempts": unknown_usage_attempts,
            "known_attempts": [
                attempt["attempt"]
                for attempt in normalized
                if _usage_is_complete(attempt["usage"])
            ],
        },
        "known_token_lower_bound": {
            **lower_bound,
            "is_complete_total": billing_complete is True,
            "unknown_attempt_count": len(unknown_usage_attempts),
        },
        "provider_call_budget": {
            "limit": provider_call_limit,
            "used": len(normalized),
            "remaining": provider_call_limit - len(normalized),
            "hard_stop": True,
            "exhausted": len(normalized) == provider_call_limit,
        },
        "execution_reliability": reliability,
    }


def assess_pair_comparability_v5(
    baseline: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any]:
    """Apply the v5 token-pair admission rule to two accounting records."""

    reasons: list[str] = []
    for label, record in (("baseline", baseline), ("candidate", candidate)):
        reliability = record.get("execution_reliability")
        success = record.get("successful_response_usage")
        if not isinstance(reliability, Mapping) or not isinstance(success, Mapping):
            reasons.append(f"{label}_accounting_invalid")
            continue
        if reliability.get("final_output_real") is not True:
            reasons.append(f"{label}_final_output_not_real")
        if reliability.get("final_output_safe_valid") is not True:
            reasons.append(f"{label}_final_output_not_safe_valid")
        if success.get("status") != "complete":
            reasons.append(f"{label}_successful_response_usage_incomplete")
        if _token_value(success.get("output_tokens")) is None:
            reasons.append(f"{label}_successful_response_output_tokens_unknown")
    if reasons:
        return {
            "status": "excluded",
            "reasons": reasons,
            "baseline_output_tokens": None,
            "candidate_output_tokens": None,
        }
    return {
        "status": "comparable",
        "reasons": [],
        "baseline_output_tokens": baseline["successful_response_usage"]["output_tokens"],
        "candidate_output_tokens": candidate["successful_response_usage"]["output_tokens"],
    }


@dataclass
class ProviderCallBudgetV5:
    """A hard per-protocol Provider-call counter."""

    limit: int
    used: int = 0

    def __post_init__(self) -> None:
        if type(self.limit) is not int or self.limit < 1:
            raise QuestionDraftPromptRecoveryProtocolV5Error(
                "Provider call budget limit must be a positive integer"
            )
        if type(self.used) is not int or not 0 <= self.used <= self.limit:
            raise QuestionDraftPromptRecoveryProtocolV5Error("Invalid used Provider call count")

    def consume(self) -> int:
        if self.used >= self.limit:
            raise QuestionDraftPromptRecoveryProtocolV5Error(
                "Provider call budget exhausted before call"
            )
        self.used += 1
        return self.used

    def snapshot(self) -> dict[str, int | bool]:
        return {
            "limit": self.limit,
            "used": self.used,
            "remaining": self.limit - self.used,
            "hard_stop": True,
            "exhausted": self.used == self.limit,
        }


ReadinessStatus = Literal["pending", "passed", "blocked"]


@dataclass
class ProviderReadinessGateV5:
    """Persistent, single-ledger gate kept outside formal A/B run directories."""

    ledger_path: Path
    provider: str
    model: str
    frozen_assets_sha256: str
    max_attempts: int = READINESS_MAX_ATTEMPTS
    _state: dict[str, Any] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_attempts != READINESS_MAX_ATTEMPTS:
            raise QuestionDraftPromptRecoveryProtocolV5Error(
                f"Readiness max attempts is frozen at {READINESS_MAX_ATTEMPTS}"
            )
        if not self.provider or not self.model or not self.frozen_assets_sha256:
            raise QuestionDraftPromptRecoveryProtocolV5Error(
                "Readiness identity and frozen asset hash are required"
            )
        self.ledger_path = Path(self.ledger_path)
        if self.ledger_path.exists():
            self._state = self._load()
            self._assert_identity()
        else:
            self._state = {
                "protocol_version": PROTOCOL_VERSION,
                "record_type": "provider_readiness_gate",
                "scope": "readiness_only_not_token_ab",
                "provider": self.provider,
                "model": self.model,
                "frozen_assets_sha256": self.frozen_assets_sha256,
                "max_attempts": self.max_attempts,
                "provider_calls_per_attempt": READINESS_CALLS_PER_ATTEMPT,
                "status": "pending",
                "attempts": [],
            }
            self._persist()

    @property
    def status(self) -> ReadinessStatus:
        return self._state["status"]

    @property
    def state(self) -> dict[str, Any]:
        return json.loads(json.dumps(self._state))

    def record_attempt(self, accounting: Mapping[str, Any]) -> ReadinessStatus:
        if self.status != "pending":
            raise QuestionDraftPromptRecoveryProtocolV5Error(
                "Readiness gate is terminal; do not create another retry ledger"
            )
        records = self._state["attempts"]
        if len(records) >= self.max_attempts:
            raise QuestionDraftPromptRecoveryProtocolV5Error("Readiness attempt budget exhausted")

        reliability = accounting.get("execution_reliability")
        success = accounting.get("successful_response_usage")
        billing = accounting.get("billing_usage_completeness")
        budget = accounting.get("provider_call_budget")
        if not all(
            isinstance(item, Mapping)
            for item in (reliability, success, billing, budget)
        ):
            raise QuestionDraftPromptRecoveryProtocolV5Error("Invalid readiness accounting")
        if budget.get("used") != READINESS_CALLS_PER_ATTEMPT:
            raise QuestionDraftPromptRecoveryProtocolV5Error(
                "Each readiness attempt must contain exactly one Provider call"
            )

        passed = (
            reliability.get("final_output_real") is True
            and reliability.get("final_output_safe_valid") is True
            and reliability.get("retry_count") == 0
            and success.get("status") == "complete"
            and billing.get("status") == "complete"
        )
        records.append(
            {
                "attempt": len(records) + 1,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "passed": passed,
                "successful_response_usage_status": success.get("status"),
                "billing_usage_completeness": billing.get("status"),
                "execution_reliability": {
                    key: reliability.get(key)
                    for key in (
                        "final_execution_mode",
                        "final_output_real",
                        "final_output_safe_valid",
                        "provider_calls",
                        "timeout_attempts",
                        "network_error_attempts",
                        "retry_count",
                        "fallback_used",
                        "deadline_terminated",
                    )
                },
            }
        )
        if passed:
            self._state["status"] = "passed"
        elif len(records) >= self.max_attempts:
            self._state["status"] = "blocked"
        self._persist()
        return self.status

    def assert_ab_start_allowed(self) -> None:
        if self.status != "passed":
            raise QuestionDraftPromptRecoveryProtocolV5Error(
                "Provider readiness has not passed; an A/B run directory must not be created"
            )

    def _assert_identity(self) -> None:
        expected = {
            "protocol_version": PROTOCOL_VERSION,
            "record_type": "provider_readiness_gate",
            "scope": "readiness_only_not_token_ab",
            "provider": self.provider,
            "model": self.model,
            "frozen_assets_sha256": self.frozen_assets_sha256,
            "max_attempts": self.max_attempts,
            "provider_calls_per_attempt": READINESS_CALLS_PER_ATTEMPT,
        }
        for key, value in expected.items():
            if self._state.get(key) != value:
                raise QuestionDraftPromptRecoveryProtocolV5Error(
                    f"Readiness ledger {key} drift detected"
                )
        if self._state.get("status") not in {"pending", "passed", "blocked"}:
            raise QuestionDraftPromptRecoveryProtocolV5Error("Invalid readiness ledger status")
        attempts = self._state.get("attempts")
        if not isinstance(attempts, list) or len(attempts) > self.max_attempts:
            raise QuestionDraftPromptRecoveryProtocolV5Error("Invalid readiness attempt ledger")

    def _load(self) -> dict[str, Any]:
        try:
            loaded = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise QuestionDraftPromptRecoveryProtocolV5Error(
                "Readiness ledger is unreadable"
            ) from exc
        if not isinstance(loaded, dict):
            raise QuestionDraftPromptRecoveryProtocolV5Error("Readiness ledger must be an object")
        return loaded

    def _persist(self) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.ledger_path.with_suffix(self.ledger_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self._state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.ledger_path)
