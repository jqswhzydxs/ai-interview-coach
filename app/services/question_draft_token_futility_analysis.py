"""Offline Phase 2.4D-C analysis of the frozen protocol v2 Pilot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from app.services.provider_usage_details import historical_usage_detail_audit


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AB1_DIR = (
    PROJECT_ROOT
    / "storage/reports/question-bank-token-phase-2-4d-b2-v2-20261022-ab1"
)
DEFAULT_READINESS_LEDGER = (
    PROJECT_ROOT
    / "storage/reports/question-bank-token-phase-2-4d-b2-readiness-20261022"
    / "provider-readiness-v2.json"
)
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "storage/reports/question-bank-token-phase-2-4d-c-offline-20261022"
)


class QuestionDraftTokenFutilityAnalysisError(RuntimeError):
    """The frozen Pilot evidence cannot support the requested offline analysis."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QuestionDraftTokenFutilityAnalysisError(
            f"Unreadable frozen evidence file: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise QuestionDraftTokenFutilityAnalysisError(
            f"Frozen evidence file must contain an object: {path}"
        )
    return value


def _percent_change(candidate: int | float, baseline: int | float) -> float:
    if baseline == 0:
        raise QuestionDraftTokenFutilityAnalysisError("Cannot divide by a zero baseline")
    return (candidate - baseline) / baseline


def _success_usage(run: Mapping[str, Any]) -> dict[str, int]:
    usage = run.get("successful_response_usage")
    if not isinstance(usage, Mapping) or usage.get("status") != "complete":
        raise QuestionDraftTokenFutilityAnalysisError(
            "Pilot paired run lacks complete successful-response usage"
        )
    result: dict[str, int] = {}
    for field in ("input_tokens", "output_tokens", "total_tokens"):
        value = usage.get(field)
        if type(value) is not int or value < 0:
            raise QuestionDraftTokenFutilityAnalysisError(
                f"Pilot paired run has invalid {field}"
            )
        result[field] = value
    return result


def _visible(run: Mapping[str, Any]) -> dict[str, int | float]:
    diagnostics = run.get("length_diagnostics")
    overall = diagnostics.get("overall") if isinstance(diagnostics, Mapping) else None
    if not isinstance(overall, Mapping):
        raise QuestionDraftTokenFutilityAnalysisError(
            "Pilot paired run lacks visible-length diagnostics"
        )
    counts = overall.get("character_counts")
    if not isinstance(counts, list) or len(counts) != 25:
        raise QuestionDraftTokenFutilityAnalysisError(
            "Pilot paired run must contain 25 visible question lengths"
        )
    if any(type(value) is not int or value < 0 for value in counts):
        raise QuestionDraftTokenFutilityAnalysisError(
            "Visible question lengths must be non-negative integers"
        )
    return {
        "question_count": len(counts),
        "character_total": sum(counts),
        "average": overall.get("average"),
        "p50": overall.get("p50"),
        "p95": overall.get("p95"),
        "max": overall.get("max"),
    }


def _run_metrics(run: Mapping[str, Any]) -> dict[str, Any]:
    usage = _success_usage(run)
    visible = _visible(run)
    billing = run.get("billing_usage_completeness")
    reliability = run.get("execution_reliability")
    if not isinstance(billing, Mapping) or not isinstance(reliability, Mapping):
        raise QuestionDraftTokenFutilityAnalysisError(
            "Pilot paired run lacks protocol v2 accounting"
        )
    return {
        "successful_response_usage": usage,
        "visible_question_characters": visible,
        "latency_ms": run.get("latency_ms"),
        "provider_calls": run.get("provider_calls"),
        "retry_count": run.get("retry_count"),
        "billing_usage_completeness": {
            "status": billing.get("status"),
            "is_complete": billing.get("is_complete"),
            "unknown_attempts": billing.get("unknown_attempts"),
        },
        "execution_reliability": {
            key: reliability.get(key)
            for key in (
                "timeout_attempts",
                "network_error_attempts",
                "failed_attempts",
                "fallback_used",
                "final_output_real",
                "final_output_safe_valid",
            )
        },
        "output_tokens_per_visible_character": (
            usage["output_tokens"] / visible["character_total"]
        ),
    }


def _pair_delta(baseline: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    baseline_usage = baseline["successful_response_usage"]
    candidate_usage = candidate["successful_response_usage"]
    baseline_chars = baseline["visible_question_characters"]["character_total"]
    candidate_chars = candidate["visible_question_characters"]["character_total"]
    output_change = _percent_change(
        candidate_usage["output_tokens"], baseline_usage["output_tokens"]
    )
    character_change = _percent_change(candidate_chars, baseline_chars)
    return {
        "input_tokens": candidate_usage["input_tokens"] - baseline_usage["input_tokens"],
        "output_tokens": candidate_usage["output_tokens"] - baseline_usage["output_tokens"],
        "total_tokens": candidate_usage["total_tokens"] - baseline_usage["total_tokens"],
        "visible_characters": candidate_chars - baseline_chars,
        "latency_ms": candidate["latency_ms"] - baseline["latency_ms"],
        "output_token_change_fraction": output_change,
        "visible_character_change_fraction": character_change,
        "change_direction_gap_percentage_points": (
            output_change - character_change
        ) * 100,
        "output_token_density_multiplier": (
            candidate["output_tokens_per_visible_character"]
            / baseline["output_tokens_per_visible_character"]
        ),
    }


def build_pilot_analysis(
    *,
    ab1_dir: Path = DEFAULT_AB1_DIR,
    readiness_ledger: Path = DEFAULT_READINESS_LEDGER,
) -> dict[str, Any]:
    manifest_path = ab1_dir / "manifest.json"
    report_path = ab1_dir / "question-draft-token-v2-report.json"
    audit_path = ab1_dir / "audit/executions.json"
    manifest = _load_object(manifest_path)
    report = _load_object(report_path)
    audit = _load_object(audit_path)
    readiness = _load_object(readiness_ledger)

    if report.get("status") != "pilot_passed":
        raise QuestionDraftTokenFutilityAnalysisError(
            "Expected the frozen ab1 operational Pilot gate to be passed"
        )
    if report.get("completion_status") != "not_started":
        raise QuestionDraftTokenFutilityAnalysisError(
            "Frozen ab1 unexpectedly records Full completion"
        )
    if readiness.get("status") != "passed":
        raise QuestionDraftTokenFutilityAnalysisError(
            "Referenced readiness ledger is not passed"
        )

    raw_runs = audit.get("runs")
    if not isinstance(raw_runs, list) or len(raw_runs) != 6:
        raise QuestionDraftTokenFutilityAnalysisError(
            "Frozen ab1 must contain exactly six paired Pilot runs"
        )
    indexed: dict[tuple[str, int, str], Mapping[str, Any]] = {}
    for run in raw_runs:
        if not isinstance(run, Mapping):
            raise QuestionDraftTokenFutilityAnalysisError("Invalid Pilot run record")
        key = (str(run.get("case_id")), int(run.get("pair", 0)), str(run.get("variant")))
        if key in indexed:
            raise QuestionDraftTokenFutilityAnalysisError("Duplicate Pilot run identity")
        indexed[key] = run

    case_ids = sorted({key[0] for key in indexed})
    pairs: list[dict[str, Any]] = []
    aggregate = {
        variant: {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "visible_characters": 0,
            "question_count": 0,
            "provider_calls": 0,
            "retry_count": 0,
            "billing_incomplete_runs": 0,
            "timeout_attempts": 0,
        }
        for variant in ("baseline", "candidate")
    }
    for case_id in case_ids:
        baseline_run = indexed.get((case_id, 1, "baseline"))
        candidate_run = indexed.get((case_id, 1, "candidate"))
        if baseline_run is None or candidate_run is None:
            raise QuestionDraftTokenFutilityAnalysisError(
                f"Incomplete Pilot pair for {case_id}"
            )
        baseline = _run_metrics(baseline_run)
        candidate = _run_metrics(candidate_run)
        pairs.append(
            {
                "case_id": case_id,
                "pair": 1,
                "comparison_status": "comparable",
                "baseline": baseline,
                "candidate": candidate,
                "candidate_minus_baseline": _pair_delta(baseline, candidate),
            }
        )
        for variant, metrics in (("baseline", baseline), ("candidate", candidate)):
            usage = metrics["successful_response_usage"]
            visible = metrics["visible_question_characters"]
            target = aggregate[variant]
            for field in ("input_tokens", "output_tokens", "total_tokens"):
                target[field] += usage[field]
            target["visible_characters"] += visible["character_total"]
            target["question_count"] += visible["question_count"]
            target["provider_calls"] += metrics["provider_calls"]
            target["retry_count"] += metrics["retry_count"]
            target["billing_incomplete_runs"] += int(
                metrics["billing_usage_completeness"]["status"] != "complete"
            )
            target["timeout_attempts"] += metrics["execution_reliability"][
                "timeout_attempts"
            ]

    for variant, totals in aggregate.items():
        totals["average_output_tokens_per_run"] = totals["output_tokens"] / 3
        totals["average_visible_characters_per_question"] = (
            totals["visible_characters"] / totals["question_count"]
        )
        totals["output_tokens_per_visible_character"] = (
            totals["output_tokens"] / totals["visible_characters"]
        )

    baseline = aggregate["baseline"]
    candidate = aggregate["candidate"]
    output_change = _percent_change(
        candidate["output_tokens"], baseline["output_tokens"]
    )
    character_change = _percent_change(
        candidate["visible_characters"], baseline["visible_characters"]
    )
    report_candidate = report["summary"]["variants"]["candidate"]
    comparison = report["summary"]["token_comparison"]
    return {
        "record_type": "phase_2_4d_c_prompt_v0_2_pilot_futility_analysis",
        "analysis_mode": "offline_only",
        "network_accessed": False,
        "source_evidence": {
            "ab1_manifest": {"path": manifest_path.relative_to(PROJECT_ROOT).as_posix(), "sha256": sha256_file(manifest_path)},
            "ab1_report": {"path": report_path.relative_to(PROJECT_ROOT).as_posix(), "sha256": sha256_file(report_path)},
            "ab1_execution_audit": {"path": audit_path.relative_to(PROJECT_ROOT).as_posix(), "sha256": sha256_file(audit_path)},
            "readiness_ledger": {"path": readiness_ledger.relative_to(PROJECT_ROOT).as_posix(), "sha256": sha256_file(readiness_ledger)},
        },
        "frozen_source_state": {
            "experiment_id": manifest.get("experiment_id"),
            "protocol_version": manifest.get("protocol_version"),
            "provider": manifest.get("provider"),
            "model": manifest.get("model"),
            "pilot_operational_gate": "passed",
            "full_executed": False,
            "blind_review_executed": False,
            "finalize_executed": False,
            "source_status_unchanged": True,
        },
        "per_pair": pairs,
        "aggregate": aggregate,
        "token_character_decoupling": {
            "candidate_output_token_change_fraction": output_change,
            "candidate_visible_character_change_fraction": character_change,
            "change_direction_gap_percentage_points": (
                output_change - character_change
            ) * 100,
            "output_token_density_multiplier": (
                candidate["output_tokens_per_visible_character"]
                / baseline["output_tokens_per_visible_character"]
            ),
            "interpretation": (
                "Visible question compression did not reduce successful-response output "
                "tokens. This is a diagnostic association and does not identify a hidden "
                "token category or Provider root cause."
            ),
        },
        "reliability_and_billing": {
            "candidate_p95_latency_ms": report_candidate["latency_ms"]["p95"],
            "candidate_max_latency_ms": report_candidate["latency_ms"]["max"],
            "candidate_retry_count": report_candidate["retry_count"],
            "candidate_timeout_attempts": report_candidate["execution_reliability"]["timeout_attempts"],
            "candidate_billing_incomplete_runs": report_candidate["billing_incomplete_runs"],
            "billing_interpretation": (
                "The Java candidate final successful-response usage remains comparable; "
                "the unknown failed timeout attempt means total billed usage is only a lower bound."
            ),
        },
        "formal_gate_boundary": {
            "comparable_pair_count": comparison["comparable_pair_count"],
            "required_comparable_pair_count": comparison["minimum_comparable_pair_count"],
            "formal_final_gates": "not_evaluable",
            "engineering_futility_is_formal_statistical_rejection": False,
        },
    }


def build_early_stop_decision(analysis: Mapping[str, Any]) -> dict[str, Any]:
    aggregate = analysis["aggregate"]
    decoupling = analysis["token_character_decoupling"]
    reliability = analysis["reliability_and_billing"]
    return {
        "record_type": "phase_2_4d_c_early_stop_decision",
        "decision_status": "stopped_for_engineering_futility",
        "decision_date": "2026-10-22",
        "source_experiment_id": analysis["frozen_source_state"]["experiment_id"],
        "source_ab1_mutated": False,
        "full_executed": False,
        "blind_review_executed": False,
        "finalize_executed": False,
        "formal_final_gate_status": "not_evaluable",
        "formal_statistical_rejection": False,
        "prompt_v0_2_promoted": False,
        "prompt_v0_3_created": False,
        "rationale": {
            "baseline_output_tokens": aggregate["baseline"]["output_tokens"],
            "candidate_output_tokens": aggregate["candidate"]["output_tokens"],
            "candidate_output_token_change_fraction": decoupling[
                "candidate_output_token_change_fraction"
            ],
            "candidate_visible_character_change_fraction": decoupling[
                "candidate_visible_character_change_fraction"
            ],
            "candidate_p95_latency_ms": reliability["candidate_p95_latency_ms"],
            "final_latency_threshold_ms": 90_000,
            "comparable_pair_count": analysis["formal_gate_boundary"][
                "comparable_pair_count"
            ],
            "required_comparable_pair_count": analysis["formal_gate_boundary"][
                "required_comparable_pair_count"
            ],
        },
        "interpretation_boundary": (
            "This new offline engineering decision stops further data collection for ab1. "
            "It does not overwrite the original pilot_passed report, claim completion of "
            "the preregistered Full, or constitute a formal statistical rejection."
        ),
    }


def build_next_experiment_options() -> dict[str, Any]:
    return {
        "record_type": "phase_2_4d_c_next_single_variable_options",
        "current_data_mixing_allowed": False,
        "prompt_v0_3_created": False,
        "options": [
            {
                "id": "fixed_max_tokens",
                "single_variable": "max_tokens",
                "schema_truncation_risk": "high until an offline-safe 25-question bound is demonstrated",
                "twenty_five_question_completeness_risk": "high near the cap",
                "cost_effect": "hard output ceiling, but failed truncated responses may waste calls",
                "latency_effect": "upper tail may improve; retries after invalid JSON may offset it",
                "comparability": "requires a new protocol and complete paired rerun",
            },
            {
                "id": "same_model_reasoning_disabled_or_bounded",
                "single_variable": "one explicit Provider-supported reasoning control",
                "schema_truncation_risk": "low if no output cap is introduced",
                "twenty_five_question_completeness_risk": "lower than fixed max_tokens, subject to quality checks",
                "cost_effect": "directly targets non-visible reasoning tokens if the Provider exposes and honors the control",
                "latency_effect": "expected to reduce generation work, but must be measured",
                "comparability": "best causal isolation; both control and treatment must be rerun under a new protocol",
                "precondition": "official model support and an observable request/response capability signal",
            },
            {
                "id": "explicit_non_reasoning_model",
                "single_variable": "model identity",
                "schema_truncation_risk": "model dependent",
                "twenty_five_question_completeness_risk": "requires new Schema and safety qualification",
                "cost_effect": "potentially predictable lower reasoning cost",
                "latency_effect": "potential improvement, with a new model reliability profile",
                "comparability": "larger capability confound; new protocol and full rerun required",
            },
            {
                "id": "same_model_controlled_generation_parameter",
                "single_variable": "one documented generation parameter other than max_tokens/reasoning",
                "schema_truncation_risk": "parameter dependent",
                "twenty_five_question_completeness_risk": "parameter dependent and must be gated",
                "cost_effect": "no guaranteed token ceiling",
                "latency_effect": "unknown until measured",
                "comparability": "good only when exactly one parameter changes in a new protocol",
            },
        ],
        "recommendation": {
            "option_id": "same_model_reasoning_disabled_or_bounded",
            "design": (
                "Keep model, Prompt v0.2, metadata v2, Schema, fixtures, temperature, "
                "timeouts and checks fixed; compare model-default reasoning with one explicit "
                "reasoning-disabled control. Rerun both arms from zero under a new protocol."
            ),
            "why": (
                "The Pilot's visible text shrank while output tokens increased, so the next "
                "experiment should isolate non-visible generation work before imposing a cap "
                "that can truncate the 25-question JSON document."
            ),
            "go_no_go_precondition": (
                "Do not create the protocol or run data unless offline capability evidence "
                "proves the exact Provider/model supports the parameter and the request path "
                "can record that it was applied."
            ),
            "historical_data_reuse": "for_context_only_not_pooled_or_compared_as_new_protocol_data",
        },
    }


def write_analysis_artifacts(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    ab1_dir: Path = DEFAULT_AB1_DIR,
    readiness_ledger: Path = DEFAULT_READINESS_LEDGER,
) -> dict[str, Path]:
    resolved_output = output_dir.resolve()
    frozen_roots = (ab1_dir.resolve(), readiness_ledger.resolve().parent)
    if any(
        resolved_output == root or resolved_output.is_relative_to(root)
        for root in frozen_roots
    ):
        raise QuestionDraftTokenFutilityAnalysisError(
            "Analysis output must not overlap frozen ab1 or readiness evidence"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    analysis = build_pilot_analysis(ab1_dir=ab1_dir, readiness_ledger=readiness_ledger)
    usage_audit = historical_usage_detail_audit()
    usage_audit["source_evidence"] = {
        relative: sha256_file(PROJECT_ROOT / relative)
        for relative in (
            "app/agents/llm_client.py",
            "app/agents/openai_compatible_client.py",
            "storage/reports/question-bank-token-phase-2-4d-b2-v2-20261022-ab1/audit/executions.json",
        )
    }
    payloads = {
        "pilot-futility-analysis.json": analysis,
        "usage-details-audit.json": usage_audit,
        "early-stop-decision.json": build_early_stop_decision(analysis),
        "next-experiment-options.json": build_next_experiment_options(),
    }
    paths: dict[str, Path] = {}
    for name, payload in payloads.items():
        path = output_dir / name
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        paths[name] = path
    return paths
