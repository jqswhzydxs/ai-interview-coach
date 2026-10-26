"""Offline-only Phase 2.4D-E-B analysis for the protocol v4 Pilot.

The analyzer reads the frozen v4 report and sanitized audit records. It never
invokes a Provider and never mutates the readiness or A/B directories.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Mapping


PROTOCOL_VERSION = "phase-2.4d-question-draft-reasoning-effort-token-v4"
ANALYSIS_VERSION = "phase-2.4d-e-b-pilot-futility-analysis-v1"
EXPECTED_CASES = {
    "backend_go_case": "Go",
    "backend_java_case": "Java",
    "backend_python_case": "Python",
}
EXPECTED_VARIANTS = {"baseline", "candidate"}
PILOT_PAIR = 1
FINAL_CANDIDATE_RUN_COUNT = 15
OUTPUT_TOKEN_LIMIT = 1800


class QuestionDraftReasoningEffortFutilityError(RuntimeError):
    """Frozen Pilot evidence does not satisfy the analysis contract."""


@dataclass(frozen=True)
class PilotFutilityArtifacts:
    analysis: dict[str, Any]
    decision: dict[str, Any]
    recommendation: dict[str, Any]


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QuestionDraftReasoningEffortFutilityError(
            f"Unable to load frozen JSON asset: {path.name}"
        ) from exc
    if not isinstance(payload, dict):
        raise QuestionDraftReasoningEffortFutilityError(
            f"Frozen JSON asset must be an object: {path.name}"
        )
    return payload


def _require_int(value: object, field: str) -> int:
    if type(value) is not int or value < 0:
        raise QuestionDraftReasoningEffortFutilityError(
            f"{field} must be an explicit non-negative integer"
        )
    return value


def _safe_detail(run: Mapping[str, Any], field: str) -> dict[str, Any]:
    details = run.get("successful_response_usage_details")
    row = details.get(field) if isinstance(details, Mapping) else None
    if not isinstance(row, Mapping):
        return {"status": "unknown", "value": None}
    status = row.get("status")
    value = row.get("value")
    if status == "available" and type(value) is int and value >= 0:
        return {"status": "available", "value": value}
    return {"status": "unknown", "value": None}


def _distribution(values: list[int | float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "mean": None, "min": None, "max": None, "range": None}
    return {
        "count": len(values),
        "mean": mean(values),
        "min": min(values),
        "max": max(values),
        "range": max(values) - min(values),
        "population_standard_deviation": pstdev(values),
    }


def _validate_report(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    if report.get("protocol_version") != PROTOCOL_VERSION:
        raise QuestionDraftReasoningEffortFutilityError("Protocol v4 identity mismatch")
    if report.get("status") != "pilot_passed":
        raise QuestionDraftReasoningEffortFutilityError(
            "Analysis requires the frozen pilot_passed state"
        )
    if report.get("completion_status") != "not_started":
        raise QuestionDraftReasoningEffortFutilityError(
            "Full must remain not_started for this early-stop analysis"
        )
    runs = report.get("runs")
    if not isinstance(runs, list) or len(runs) != 6:
        raise QuestionDraftReasoningEffortFutilityError(
            "Pilot evidence must contain exactly six paired executions"
        )
    seen: set[tuple[str, str]] = set()
    for run in runs:
        if not isinstance(run, dict):
            raise QuestionDraftReasoningEffortFutilityError("Run must be an object")
        case_id = run.get("case_id")
        variant = run.get("variant")
        if case_id not in EXPECTED_CASES or variant not in EXPECTED_VARIANTS:
            raise QuestionDraftReasoningEffortFutilityError("Unexpected Pilot case or variant")
        if run.get("pair") != PILOT_PAIR:
            raise QuestionDraftReasoningEffortFutilityError("Only Pilot pair 1 is allowed")
        key = (case_id, variant)
        if key in seen:
            raise QuestionDraftReasoningEffortFutilityError("Duplicate Pilot arm")
        seen.add(key)
        reliability = run.get("execution_reliability")
        checks = run.get("content_checks")
        if not isinstance(reliability, Mapping) or not isinstance(checks, Mapping):
            raise QuestionDraftReasoningEffortFutilityError("Run checks are incomplete")
        if not (
            run.get("execution_mode") == "real"
            and reliability.get("final_output_safe_valid") is True
            and all(value == "passed" for value in checks.values())
        ):
            raise QuestionDraftReasoningEffortFutilityError(
                "All six Pilot outputs must be real and safe-valid"
            )
    if len(seen) != 6:
        raise QuestionDraftReasoningEffortFutilityError("Pilot arms are incomplete")
    return runs


def _audit_failures(audit: Mapping[str, Any]) -> dict[tuple[str, str, int], list[dict[str, Any]]]:
    provider_calls = audit.get("provider_calls")
    if not isinstance(provider_calls, list):
        raise QuestionDraftReasoningEffortFutilityError("Audit Provider calls are missing")
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for call in provider_calls:
        if not isinstance(call, Mapping) or call.get("status") != "failed":
            continue
        key = (call.get("case_id"), call.get("variant"), call.get("pair"))
        if key[0] not in EXPECTED_CASES or key[1] not in EXPECTED_VARIANTS:
            continue
        usage = call.get("token_usage")
        usage = usage if isinstance(usage, Mapping) else {}
        grouped[key].append(
            {
                "failure_category": call.get("failure_category"),
                "exception_type": call.get("exception_type"),
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "usage_status": call.get("token_usage_status", "not_available"),
            }
        )
    return grouped


def _arm_record(
    run: Mapping[str, Any],
    failures: list[dict[str, Any]],
) -> dict[str, Any]:
    lengths = run.get("length_diagnostics")
    if not isinstance(lengths, Mapping) or not isinstance(lengths.get("overall"), Mapping):
        raise QuestionDraftReasoningEffortFutilityError("Length diagnostics are missing")
    overall = lengths["overall"]
    return {
        "input_tokens": _require_int(run.get("input_tokens"), "input_tokens"),
        "output_tokens": _require_int(run.get("output_tokens"), "output_tokens"),
        "total_tokens": _require_int(run.get("total_tokens"), "total_tokens"),
        "reasoning_tokens": _safe_detail(run, "reasoning_tokens"),
        "visible_completion_tokens": _safe_detail(run, "visible_completion_tokens"),
        "cached_input_tokens": _safe_detail(run, "cached_input_tokens"),
        "latency_ms": _require_int(run.get("latency_ms"), "latency_ms"),
        "provider_calls": _require_int(run.get("provider_calls"), "provider_calls"),
        "retry_count": _require_int(run.get("retry_count"), "retry_count"),
        "billing_usage_completeness": run.get("billing_usage_completeness"),
        "known_token_lower_bound": run.get("known_token_lower_bound"),
        "failed_attempts": failures,
        "question_length": {
            "count": _require_int(overall.get("count"), "question_count"),
            "average_characters": overall.get("average"),
            "p50_characters": overall.get("p50"),
            "p95_characters": overall.get("p95"),
            "max_characters": overall.get("max"),
            "above_module_recommended": lengths.get(
                "above_module_recommended_total"
            ),
            "by_module": lengths.get("by_module"),
        },
        "content_checks": run.get("content_checks"),
    }


def analyze_v4_pilot(
    report_path: Path,
    audit_path: Path,
) -> PilotFutilityArtifacts:
    """Create descriptive Pilot analysis without changing the source assets."""

    report_hash_before = file_sha256(report_path)
    audit_hash_before = file_sha256(audit_path)
    report = _load_json(report_path)
    audit = _load_json(audit_path)
    if audit.get("protocol_version") != PROTOCOL_VERSION:
        raise QuestionDraftReasoningEffortFutilityError("Audit protocol mismatch")
    runs = _validate_report(report)
    failures = _audit_failures(audit)

    indexed = {(run["case_id"], run["variant"]): run for run in runs}
    pairs: list[dict[str, Any]] = []
    by_variant: dict[str, list[dict[str, Any]]] = {variant: [] for variant in EXPECTED_VARIANTS}
    for case_id, stack in EXPECTED_CASES.items():
        baseline = _arm_record(
            indexed[(case_id, "baseline")],
            failures.get((case_id, "baseline", PILOT_PAIR), []),
        )
        candidate = _arm_record(
            indexed[(case_id, "candidate")],
            failures.get((case_id, "candidate", PILOT_PAIR), []),
        )
        by_variant["baseline"].append(baseline)
        by_variant["candidate"].append(candidate)
        pairs.append(
            {
                "case_id": case_id,
                "technology_stack": stack,
                "pair": PILOT_PAIR,
                "baseline_high": baseline,
                "candidate_low": candidate,
                "descriptive_deltas": {
                    "output_tokens_candidate_minus_baseline": (
                        candidate["output_tokens"] - baseline["output_tokens"]
                    ),
                    "paired_output_token_reduction": (
                        baseline["output_tokens"] - candidate["output_tokens"]
                    )
                    / baseline["output_tokens"],
                    "reasoning_tokens_candidate_minus_baseline": (
                        candidate["reasoning_tokens"]["value"]
                        - baseline["reasoning_tokens"]["value"]
                    ),
                    "average_question_characters_candidate_minus_baseline": (
                        candidate["question_length"]["average_characters"]
                        - baseline["question_length"]["average_characters"]
                    ),
                },
            }
        )

    variant_summary: dict[str, Any] = {}
    for variant, arms in by_variant.items():
        outputs = [arm["output_tokens"] for arm in arms]
        reasoning = [arm["reasoning_tokens"]["value"] for arm in arms]
        lengths = [
            value
            for arm in arms
            for value in arm["question_length"]["by_module"].values()
            for value in value["character_counts"]
        ]
        variant_summary[variant] = {
            "input_tokens_total": sum(arm["input_tokens"] for arm in arms),
            "output_tokens_total": sum(outputs),
            "output_tokens_mean": mean(outputs),
            "total_tokens_total": sum(arm["total_tokens"] for arm in arms),
            "reasoning_tokens_total": sum(reasoning),
            "reasoning_tokens_distribution": _distribution(reasoning),
            "visible_completion_tokens": {
                "status": "unknown",
                "values": [None, None, None],
                "derived_by_subtraction": False,
            },
            "latency_ms": _distribution([arm["latency_ms"] for arm in arms]),
            "retry_count": sum(arm["retry_count"] for arm in arms),
            "billing_incomplete_runs": sum(
                arm["billing_usage_completeness"]["status"] == "incomplete"
                for arm in arms
            ),
            "question_length": {
                "question_count": len(lengths),
                "average_characters": mean(lengths),
                "min_characters": min(lengths),
                "max_characters": max(lengths),
                "above_module_recommended": sum(
                    arm["question_length"]["above_module_recommended"] for arm in arms
                ),
                "token_or_quality_proxy": False,
            },
        }

    baseline_output = variant_summary["baseline"]["output_tokens_total"]
    candidate_output = variant_summary["candidate"]["output_tokens_total"]
    descriptive_reduction = (baseline_output - candidate_output) / baseline_output
    used_candidate_runs = len(by_variant["candidate"])
    remaining_runs = FINAL_CANDIDATE_RUN_COUNT - used_candidate_runs
    final_budget = FINAL_CANDIDATE_RUN_COUNT * OUTPUT_TOKEN_LIMIT
    remaining_budget = final_budget - candidate_output
    required_remaining_mean = remaining_budget / remaining_runs
    baseline_chars = variant_summary["baseline"]["question_length"][
        "average_characters"
    ]
    candidate_chars = variant_summary["candidate"]["question_length"][
        "average_characters"
    ]

    analysis = {
        "record_type": "phase_2_4d_e_b_pilot_futility_analysis",
        "analysis_version": ANALYSIS_VERSION,
        "source": {
            "protocol_version": PROTOCOL_VERSION,
            "report_path": report_path.as_posix(),
            "report_sha256": report_hash_before,
            "audit_path": audit_path.as_posix(),
            "audit_sha256": audit_hash_before,
            "original_status": "pilot_passed",
            "original_full_status": "not_started",
        },
        "gate_interpretation": {
            "pilot_execution_gate": "passed",
            "formal_full_gates": "not_evaluable",
            "formal_token_gate": "not_evaluable",
            "comparable_pairs": 3,
            "required_comparable_pairs": 12,
            "formal_statistical_rejection": False,
        },
        "pairs": pairs,
        "variant_summary": variant_summary,
        "descriptive_token_result": {
            "baseline_high_output_tokens_total": baseline_output,
            "candidate_low_output_tokens_total": candidate_output,
            "candidate_low_output_tokens_mean": candidate_output / used_candidate_runs,
            "paired_output_token_reduction": descriptive_reduction,
            "formal_gate_value": None,
            "formal_gate_status": "not_evaluable",
        },
        "absolute_target_feasibility": {
            "final_candidate_run_count": FINAL_CANDIDATE_RUN_COUNT,
            "target_mean_output_tokens_lte": OUTPUT_TOKEN_LIMIT,
            "target_total_output_tokens_lte": final_budget,
            "pilot_candidate_output_tokens_used": candidate_output,
            "remaining_candidate_runs": remaining_runs,
            "remaining_output_token_allowance": remaining_budget,
            "required_remaining_mean_output_tokens_lte": required_remaining_mean,
            "pilot_candidate_min_output_tokens": min(
                arm["output_tokens"] for arm in by_variant["candidate"]
            ),
            "engineering_assessment": "futile_trajectory",
            "mathematical_impossibility_claimed": False,
        },
        "reasoning_variability": {
            "baseline_high_total": variant_summary["baseline"][
                "reasoning_tokens_total"
            ],
            "candidate_low_total": variant_summary["candidate"][
                "reasoning_tokens_total"
            ],
            "candidate_low_distribution": variant_summary["candidate"][
                "reasoning_tokens_distribution"
            ],
            "assessment": "low effort remains highly variable across stacks",
            "causal_claim": False,
        },
        "visible_question_length": {
            "baseline_average_characters": baseline_chars,
            "candidate_average_characters": candidate_chars,
            "candidate_relative_increase": (candidate_chars - baseline_chars)
            / baseline_chars,
            "candidate_above_module_recommended": variant_summary["candidate"][
                "question_length"
            ]["above_module_recommended"],
            "candidate_question_count": 75,
            "interpretation": (
                "candidate questions are descriptively longer while output tokens remain "
                "far above the absolute gate"
            ),
            "token_proxy": False,
            "quality_proxy": False,
            "causal_claim": False,
        },
        "usage_policy": {
            "visible_completion_tokens": "unknown",
            "output_minus_reasoning_derivation_used": False,
            "missing_fields_imputed_as_zero": False,
            "known_tokens_are_lower_bound_when_billing_incomplete": True,
        },
        "reliability": {
            "all_final_outputs_real_safe": True,
            "schema_assembler_count_stack_duplicate_evidence_failures": 0,
            "candidate_p95_latency_ms": report["summary"]["variants"]["candidate"][
                "latency_ms"
            ]["p95"],
            "candidate_max_latency_ms": report["summary"]["variants"]["candidate"][
                "latency_ms"
            ]["max"],
            "candidate_network_failures": 1,
            "candidate_retries": 1,
            "billing_incomplete_runs": 1,
            "billing_total_semantics": "known_lower_bound_only",
        },
        "source_hashes_unchanged_during_analysis": (
            report_hash_before == file_sha256(report_path)
            and audit_hash_before == file_sha256(audit_path)
        ),
    }

    decision = {
        "record_type": "phase_2_4d_e_b_early_stop_decision",
        "status": "stopped_for_engineering_futility",
        "source_protocol": PROTOCOL_VERSION,
        "source_report_sha256": report_hash_before,
        "pilot_execution_gate": "passed",
        "formal_full_gates": "not_evaluable",
        "formal_token_gate": "not_evaluable",
        "formal_statistical_rejection": False,
        "decision_basis": {
            "candidate_pilot_mean_output_tokens": candidate_output / used_candidate_runs,
            "required_remaining_mean_output_tokens_lte": required_remaining_mean,
            "pilot_candidate_min_output_tokens": min(
                arm["output_tokens"] for arm in by_variant["candidate"]
            ),
            "candidate_reasoning_tokens_range": variant_summary["candidate"][
                "reasoning_tokens_distribution"
            ]["range"],
            "candidate_questions_above_recommended": 38,
        },
        "actions": {
            "run_full": False,
            "generate_blind_review": False,
            "execute_finalize": False,
            "promote_low_effort_candidate": False,
            "modify_original_v4_assets": False,
            "production_default_changed": False,
        },
        "wording_constraint": (
            "engineering early stop; not a completed Full or formal statistical rejection"
        ),
    }

    recommendation = _next_recommendation(report_hash_before)
    return PilotFutilityArtifacts(
        analysis=analysis,
        decision=decision,
        recommendation=recommendation,
    )


def _next_recommendation(source_report_sha256: str) -> dict[str, Any]:
    options = [
        {
            "option": "continue_protocol_v4_full",
            "recommendation": "reject_for_engineering_futility",
            "benefit": "would make the registered v4 gates formally evaluable",
            "risk": (
                "12 remaining candidate runs would need mean output tokens <=1062.5, "
                "below the Pilot minimum of 2171; it also spends calls before quality review"
            ),
        },
        {
            "option": "set_max_tokens",
            "recommendation": "defer",
            "benefit": "creates a provable per-request output ceiling",
            "risk": (
                "may truncate JSON or the 25-question bank; changing max_tokens requires a "
                "new protocol and complete rerun"
            ),
        },
        {
            "option": "non_thinking_plus_new_prompt",
            "recommendation": "preferred_next_single_variable_protocol",
            "benefit": (
                "holds the lower-token non-thinking mode fixed while testing whether Prompt "
                "v0.3 can recover personalization, coverage, and training value"
            ),
            "risk": (
                "quality recovery is unproven; both arms require fresh complete data and "
                "independent blind review"
            ),
        },
        {
            "option": "deterministic_expansion",
            "recommendation": "defer",
            "benefit": "could add controlled detail after a concise model draft",
            "risk": (
                "changes generation architecture and may introduce repetitive or generic text; "
                "requires its own protocol"
            ),
        },
        {
            "option": "change_model",
            "recommendation": "defer",
            "benefit": "may offer a different quality/token frontier",
            "risk": (
                "changes Provider behavior and comparability more broadly and requires new "
                "readiness plus complete paired data"
            ),
        },
    ]
    return {
        "record_type": "phase_2_4d_e_b_next_single_variable_recommendation",
        "source_report_sha256": source_report_sha256,
        "recommended_direction": "non_thinking_prompt_v0_2_vs_v0_3",
        "strict_single_variable": "prompt_text",
        "proposed_design_only": {
            "baseline": {
                "thinking": {"type": "disabled"},
                "prompt": "question_bank_draft_agent_v0.2",
            },
            "candidate": {
                "thinking": {"type": "disabled"},
                "prompt": "question_bank_draft_agent_v0.3",
                "targeted_dimensions": [
                    "personalization",
                    "coverage",
                    "training_value",
                ],
            },
            "all_other_fields_identical": True,
            "both_arms_fully_rerun": True,
            "reuse_v3_samples": False,
            "reuse_v4_samples": False,
        },
        "rationale": (
            "Protocol v3 established a strong non-thinking token/latency signal but failed "
            "text quality; a prompt-only experiment can directly test quality recovery while "
            "holding non-thinking fixed"
        ),
        "options": options,
        "prohibitions": {
            "relax_text_quality_threshold": True,
            "mix_v3_v4_data": True,
            "use_question_length_as_token_proxy": True,
            "use_question_length_as_quality_proxy": True,
        },
        "implementation_status": {
            "prompt_v0_3_created": False,
            "new_runner_created": False,
            "real_experiment_started": False,
        },
    }


def write_analysis_artifacts(
    artifacts: PilotFutilityArtifacts,
    output_dir: Path,
) -> dict[str, Path]:
    """Write only derived files to an already separate offline directory."""

    output_dir.mkdir(parents=True, exist_ok=True)
    payloads = {
        "pilot-futility-analysis.json": artifacts.analysis,
        "early-stop-decision.json": artifacts.decision,
        "next-single-variable-recommendation.json": artifacts.recommendation,
    }
    result: dict[str, Path] = {}
    for name, payload in payloads.items():
        path = output_dir / name
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result[name] = path
    return result

