"""Offline final analysis for the frozen Phase 2.4D protocol v3 experiment."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_READINESS_LEDGER = (
    PROJECT_ROOT
    / "storage/reports/question-bank-token-phase-2-4d-d-readiness-20261023"
    / "provider-readiness-v3.json"
)
DEFAULT_AB1_DIR = (
    PROJECT_ROOT
    / "storage/reports/question-bank-token-phase-2-4d-d-v3-20261023-ab1"
)
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "storage/reports/question-bank-token-phase-2-4d-d-b-offline-20261023"
)
PROTOCOL_VERSION = "phase-2.4d-question-draft-reasoning-token-v3"
ANALYSIS_VERSION = "phase-2.4d-d-b-final-analysis-v1"
TEXT_DIMENSIONS = (
    "personalization",
    "technical_correctness_and_stack_boundary",
    "coverage_and_substantive_diversity",
    "interview_training_value",
    "clarity",
)
MODULE_RANGES = {
    "self_intro": (30, 80),
    "professional": (45, 105),
    "behavior_project": (40, 100),
}
CASE_LABELS = {
    "backend_go_case": "Go",
    "backend_java_case": "Java",
    "backend_python_case": "Python",
}


class QuestionDraftReasoningFinalAnalysisError(RuntimeError):
    """The frozen v3 evidence cannot support the requested offline analysis."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QuestionDraftReasoningFinalAnalysisError(
            f"Unreadable frozen evidence file: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise QuestionDraftReasoningFinalAnalysisError(
            f"Frozen evidence must contain an object: {path}"
        )
    return value


def _round(value: float | int | None, digits: int = 6) -> float | int | None:
    if value is None or isinstance(value, int):
        return value
    return round(value, digits)


def _avg(values: Sequence[float | int]) -> float:
    if not values:
        raise QuestionDraftReasoningFinalAnalysisError("Cannot average an empty sample")
    return float(mean(values))


def _percentile(values: Sequence[float | int], quantile: float) -> float | int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * quantile) - 1)
    return ordered[index]


def _pearson(xs: Sequence[float | int], ys: Sequence[float | int]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    x_mean, y_mean = _avg(xs), _avg(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    x_sum = sum((x - x_mean) ** 2 for x in xs)
    y_sum = sum((y - y_mean) ** 2 for y in ys)
    denominator = math.sqrt(x_sum * y_sum)
    return None if denominator == 0 else numerator / denominator


def _ranks(values: Sequence[float | int]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    result = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][1] == ordered[start][1]:
            end += 1
        average_rank = ((start + 1) + end) / 2
        for index in range(start, end):
            result[ordered[index][0]] = average_rank
        start = end
    return result


def _correlation(xs: Sequence[float | int], ys: Sequence[float | int]) -> dict[str, Any]:
    return {
        "sample_count": len(xs),
        "pearson_r": _round(_pearson(xs, ys)),
        "spearman_rho": _round(_pearson(_ranks(xs), _ranks(ys))),
    }


def _score_distribution(scores: Sequence[int | float]) -> dict[str, Any]:
    counts = Counter(scores)
    return {
        "count": len(scores),
        "mean": _round(_avg(scores)),
        "p50": _percentile(scores, 0.50),
        "p95": _percentile(scores, 0.95),
        "min": min(scores),
        "max": max(scores),
        "counts": {str(score): counts.get(score, 0) for score in range(1, 6)},
        "fractions": {
            str(score): _round(counts.get(score, 0) / len(scores))
            for score in range(1, 6)
        },
    }


def _paths(ab1_dir: Path, readiness_ledger: Path) -> dict[str, Path]:
    return {
        "readiness_v3": readiness_ledger,
        "manifest": ab1_dir / "manifest.json",
        "audit": ab1_dir / "audit/executions.json",
        "private_blinding_map": ab1_dir / "audit/private-blinding-map.json",
        "blind_review_input": ab1_dir / "blind-review/question-review-packet.json",
        "blind_review_template": ab1_dir / "blind-review/question-review-template.json",
        "completed_review": ab1_dir / "blind-review/question-review-completed.json",
        "final_report_json": ab1_dir / "question-draft-reasoning-v3-report.json",
        "final_report_markdown": ab1_dir / "question-draft-reasoning-v3-report.md",
    }


def _source_hashes(paths: Mapping[str, Path]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name, path in paths.items():
        if not path.is_file():
            raise QuestionDraftReasoningFinalAnalysisError(
                f"Missing frozen v3 asset: {name}"
            )
        result[name] = sha256_file(path)
    return result


def _validate_finalized_source(
    *,
    readiness: Mapping[str, Any],
    manifest: Mapping[str, Any],
    report: Mapping[str, Any],
    review: Mapping[str, Any],
    completed_review_sha256: str,
) -> None:
    if readiness.get("protocol_version") != PROTOCOL_VERSION or readiness.get("status") != "passed":
        raise QuestionDraftReasoningFinalAnalysisError("Frozen readiness v3 is not passed")
    expected = {
        "protocol_version": PROTOCOL_VERSION,
        "status": "completed",
        "completion_status": "complete",
    }
    for name, source in (("manifest", manifest), ("report", report)):
        if any(source.get(key) != value for key, value in expected.items()):
            raise QuestionDraftReasoningFinalAnalysisError(
                f"Frozen {name} is not a finalized protocol v3 record"
            )
    thresholds = report.get("thresholds")
    if not isinstance(thresholds, Mapping) or thresholds.get("verdict") != "fail":
        raise QuestionDraftReasoningFinalAnalysisError(
            "Frozen protocol v3 verdict must be fail"
        )
    evaluator = review.get("evaluator")
    if not isinstance(evaluator, Mapping) or evaluator.get("type") != "AI":
        raise QuestionDraftReasoningFinalAnalysisError(
            "Completed review must explicitly identify an AI evaluator"
        )
    source_sha = manifest.get("review", {}).get("source_sha256")
    if source_sha != completed_review_sha256:
        raise QuestionDraftReasoningFinalAnalysisError(
            "Manifest completed-review hash does not match the frozen review"
        )


def _index_rows(
    manifest: Mapping[str, Any],
    private_map: Mapping[str, Any],
    review: Mapping[str, Any],
) -> list[dict[str, Any]]:
    mappings = private_map.get("mapping")
    submissions = manifest.get("submissions")
    runs = manifest.get("runs")
    reviews = review.get("submissions")
    if not all(isinstance(value, list) and len(value) == 30 for value in (mappings, submissions, runs, reviews)):
        raise QuestionDraftReasoningFinalAnalysisError(
            "Finalized v3 evidence must contain 30 mappings, submissions, runs, and reviews"
        )
    map_by_id = {row["submission_id"]: row for row in mappings}
    submission_by_id = {row["submission_id"]: row for row in submissions}
    review_by_id = {row["submission_id"]: row for row in reviews}
    run_by_key = {
        (row["variant"], row["case_id"], row["pair"]): row for row in runs
    }
    if not (len(map_by_id) == len(submission_by_id) == len(review_by_id) == len(run_by_key) == 30):
        raise QuestionDraftReasoningFinalAnalysisError("Duplicate or missing v3 identities")

    rows: list[dict[str, Any]] = []
    for submission_id, mapping in map_by_id.items():
        variant = mapping.get("variant")
        case_id = mapping.get("case_id")
        pair = mapping.get("pair")
        if variant not in {"baseline", "candidate"} or case_id not in CASE_LABELS:
            raise QuestionDraftReasoningFinalAnalysisError("Invalid private unblinding entry")
        submission = submission_by_id.get(submission_id)
        scored = review_by_id.get(submission_id)
        run = run_by_key.get((variant, case_id, pair))
        if submission is None or scored is None or run is None:
            raise QuestionDraftReasoningFinalAnalysisError("Incomplete unblinded join")
        questions = submission.get("questions")
        metadata_scores = scored.get("metadata_fit_scores")
        text_scores = scored.get("text_scores")
        if not isinstance(questions, list) or len(questions) != 25:
            raise QuestionDraftReasoningFinalAnalysisError("Each bank must contain 25 questions")
        if not isinstance(metadata_scores, list) or len(metadata_scores) != 25:
            raise QuestionDraftReasoningFinalAnalysisError(
                "Each reviewed bank must contain 25 metadata-fit scores"
            )
        if not isinstance(text_scores, Mapping) or set(text_scores) != set(TEXT_DIMENSIONS):
            raise QuestionDraftReasoningFinalAnalysisError("Invalid text quality dimensions")
        question_rows = []
        for question, metadata_score in zip(questions, metadata_scores):
            module = question.get("module")
            question_text = question.get("question_text")
            if module not in MODULE_RANGES or not isinstance(question_text, str):
                raise QuestionDraftReasoningFinalAnalysisError(
                    "Question module or text is invalid"
                )
            if type(metadata_score) not in {int, float} or not 1 <= metadata_score <= 5:
                raise QuestionDraftReasoningFinalAnalysisError("Invalid metadata-fit score")
            question_rows.append(
                {
                    "module": module,
                    "character_count": len(question_text),
                    "metadata_fit_score": metadata_score,
                }
            )
        normalized_text_scores = {}
        for dimension in TEXT_DIMENSIONS:
            score = text_scores[dimension]
            if type(score) not in {int, float} or not 1 <= score <= 5:
                raise QuestionDraftReasoningFinalAnalysisError("Invalid text quality score")
            normalized_text_scores[dimension] = score
        rows.append(
            {
                "variant": variant,
                "case_id": case_id,
                "pair": pair,
                "text_scores": normalized_text_scores,
                "text_quality_mean": _avg(list(normalized_text_scores.values())),
                "metadata_fit_mean": _avg(metadata_scores),
                "mean_question_characters": _avg(
                    [row["character_count"] for row in question_rows]
                ),
                "questions": question_rows,
                "output_tokens": run.get("output_tokens"),
                "latency_ms": run.get("latency_ms"),
                "run": run,
            }
        )
    return sorted(rows, key=lambda row: (row["case_id"], row["pair"], row["variant"]))


def _variant_summary(rows: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    selected = [row for row in rows if row["variant"] == variant]
    metadata = [q["metadata_fit_score"] for row in selected for q in row["questions"]]
    return {
        "submission_count": len(selected),
        "question_count": len(metadata),
        "text_quality_mean": _round(_avg([row["text_quality_mean"] for row in selected])),
        "text_dimensions": {
            dimension: _round(_avg([row["text_scores"][dimension] for row in selected]))
            for dimension in TEXT_DIMENSIONS
        },
        "metadata_fit": _score_distribution(metadata),
        "mean_question_characters": _round(
            _avg([q["character_count"] for row in selected for q in row["questions"]])
        ),
        "mean_output_tokens": _round(_avg([row["output_tokens"] for row in selected])),
    }


def _pairwise(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    indexed = {
        (row["case_id"], row["pair"], row["variant"]): row for row in rows
    }
    result = []
    outcomes: Counter[str] = Counter()
    available_case_ids = [
        case_id
        for case_id in CASE_LABELS
        if any(key[0] == case_id for key in indexed)
    ]
    for case_id in available_case_ids:
        for pair in range(1, 6):
            baseline = indexed[(case_id, pair, "baseline")]
            candidate = indexed[(case_id, pair, "candidate")]
            delta = candidate["text_quality_mean"] - baseline["text_quality_mean"]
            outcome = "win" if delta > 0 else "loss" if delta < 0 else "tie"
            outcomes[outcome] += 1
            result.append(
                {
                    "stack": CASE_LABELS[case_id],
                    "case_id": case_id,
                    "pair": pair,
                    "baseline_text_quality": _round(baseline["text_quality_mean"]),
                    "candidate_text_quality": _round(candidate["text_quality_mean"]),
                    "candidate_minus_baseline": _round(delta),
                    "candidate_outcome": outcome,
                    "baseline_mean_question_characters": _round(
                        baseline["mean_question_characters"]
                    ),
                    "candidate_mean_question_characters": _round(
                        candidate["mean_question_characters"]
                    ),
                    "baseline_output_tokens": baseline["output_tokens"],
                    "candidate_output_tokens": candidate["output_tokens"],
                }
            )
    return result, {key: outcomes.get(key, 0) for key in ("win", "tie", "loss")}


def _by_stack(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for case_id, label in CASE_LABELS.items():
        case_rows = [row for row in rows if row["case_id"] == case_id]
        variants = {}
        for variant in ("baseline", "candidate"):
            selected = [row for row in case_rows if row["variant"] == variant]
            variants[variant] = {
                "submission_count": len(selected),
                "text_quality_mean": _round(
                    _avg([row["text_quality_mean"] for row in selected])
                ),
                "text_dimensions": {
                    dimension: _round(
                        _avg([row["text_scores"][dimension] for row in selected])
                    )
                    for dimension in TEXT_DIMENSIONS
                },
                "metadata_fit_mean": _round(
                    _avg(
                        [
                            q["metadata_fit_score"]
                            for row in selected
                            for q in row["questions"]
                        ]
                    )
                ),
                "mean_question_characters": _round(
                    _avg(
                        [
                            q["character_count"]
                            for row in selected
                            for q in row["questions"]
                        ]
                    )
                ),
                "mean_output_tokens": _round(
                    _avg([row["output_tokens"] for row in selected])
                ),
            }
        pair_rows, outcomes = _pairwise(case_rows)
        result[label] = {
            "case_id": case_id,
            **variants,
            "candidate_minus_baseline": {
                "text_quality": _round(
                    variants["candidate"]["text_quality_mean"]
                    - variants["baseline"]["text_quality_mean"]
                ),
                "metadata_fit": _round(
                    variants["candidate"]["metadata_fit_mean"]
                    - variants["baseline"]["metadata_fit_mean"]
                ),
                "mean_question_characters": _round(
                    variants["candidate"]["mean_question_characters"]
                    - variants["baseline"]["mean_question_characters"]
                ),
                "text_dimensions": {
                    dimension: _round(
                        variants["candidate"]["text_dimensions"][dimension]
                        - variants["baseline"]["text_dimensions"][dimension]
                    )
                    for dimension in TEXT_DIMENSIONS
                },
            },
            "paired_text_quality": outcomes,
            "pairs": pair_rows,
        }
    return result


def _by_module(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for module, (recommended_min, recommended_max) in MODULE_RANGES.items():
        variants = {}
        for variant in ("baseline", "candidate"):
            questions = [
                q
                for row in rows
                if row["variant"] == variant
                for q in row["questions"]
                if q["module"] == module
            ]
            lengths = [q["character_count"] for q in questions]
            scores = [q["metadata_fit_score"] for q in questions]
            variants[variant] = {
                "question_count": len(questions),
                "length": {
                    "mean": _round(_avg(lengths)),
                    "p50": _percentile(lengths, 0.50),
                    "p95": _percentile(lengths, 0.95),
                    "max": max(lengths),
                    "below_recommended": sum(value < recommended_min for value in lengths),
                    "above_recommended": sum(value > recommended_max for value in lengths),
                },
                "metadata_fit": _score_distribution(scores),
                "length_vs_metadata_fit": _correlation(lengths, scores),
            }
        result[module] = {
            "recommended_length": {"min": recommended_min, "max": recommended_max},
            **variants,
            "candidate_minus_baseline": {
                "mean_characters": _round(
                    variants["candidate"]["length"]["mean"]
                    - variants["baseline"]["length"]["mean"]
                ),
                "metadata_fit_mean": _round(
                    variants["candidate"]["metadata_fit"]["mean"]
                    - variants["baseline"]["metadata_fit"]["mean"]
                ),
            },
        }
    return result


def _correlations(rows: list[dict[str, Any]]) -> dict[str, Any]:
    bank_result = {}
    question_result = {}
    for group in ("all", "baseline", "candidate"):
        selected = rows if group == "all" else [row for row in rows if row["variant"] == group]
        bank_result[group] = _correlation(
            [row["mean_question_characters"] for row in selected],
            [row["text_quality_mean"] for row in selected],
        )
        question_result[group] = _correlation(
            [q["character_count"] for row in selected for q in row["questions"]],
            [q["metadata_fit_score"] for row in selected for q in row["questions"]],
        )
    return {
        "bank_mean_question_characters_vs_text_quality": bank_result,
        "question_characters_vs_metadata_fit": question_result,
        "interpretation": (
            "These are descriptive associations in this 30-bank experiment. "
            "They do not establish that question length caused any score change."
        ),
    }


def _timeout_record(rows: list[dict[str, Any]], report: Mapping[str, Any]) -> dict[str, Any]:
    retry_rows = [row for row in rows if row["run"].get("retry_count")]
    if len(retry_rows) != 1:
        raise QuestionDraftReasoningFinalAnalysisError(
            "Expected exactly one retried v3 execution"
        )
    row = retry_rows[0]
    run = row["run"]
    if row["variant"] != "baseline" or run.get("failure_types") != {"timeout": 1}:
        raise QuestionDraftReasoningFinalAnalysisError(
            "Expected the single retry to be the baseline timeout"
        )
    usage = run.get("successful_response_usage")
    billing = run.get("billing_usage_completeness")
    lower_bound = run.get("known_token_lower_bound")
    if not all(isinstance(value, Mapping) for value in (usage, billing, lower_bound)):
        raise QuestionDraftReasoningFinalAnalysisError("Retry accounting is incomplete")
    token_summary = report["summary"]["token_comparison"]
    return {
        "variant": "baseline",
        "stack": CASE_LABELS[row["case_id"]],
        "case_id": row["case_id"],
        "pair": row["pair"],
        "provider_calls": run.get("provider_calls"),
        "retry_count": run.get("retry_count"),
        "timeout_attempts": 1,
        "failed_attempt_usage": "unknown",
        "successful_response_usage": dict(usage),
        "successful_response_usage_complete": usage.get("status") == "complete",
        "billing_usage_completeness": dict(billing),
        "known_token_lower_bound": dict(lower_bound),
        "billing_total_interpretation": "lower_bound_only",
        "successful_response_token_pair_comparable": True,
        "registered_token_comparison_status": token_summary.get("status"),
        "effect_on_registered_successful_response_token_conclusion": "none",
        "reason": (
            "The failed timeout attempt has unknown usage, while the final real, safe "
            "response has complete input/output/total usage. Protocol v3 compares final "
            "successful-response output tokens and reports billing totals separately."
        ),
    }


def build_final_decision(report: Mapping[str, Any], evaluator: Mapping[str, Any]) -> dict[str, Any]:
    summary = report["summary"]
    token = summary["token_comparison"]
    candidate = summary["variants"]["candidate"]
    quality = summary["quality"]
    return {
        "record_type": "phase_2_4d_d_b_final_decision",
        "analysis_version": ANALYSIS_VERSION,
        "decision_date": "2026-10-23",
        "protocol": PROTOCOL_VERSION,
        "source_finalized": True,
        "source_verdict": report["thresholds"]["verdict"],
        "final_decision": "fail",
        "candidate_promotion": "denied",
        "production_integration": False,
        "frontend_stage_entered": False,
        "production_default_question_bank_agent_changed": False,
        "re_finalize_performed": False,
        "frozen_source_modified": False,
        "rejected_candidate": {
            "prompt": "question_bank_draft_agent_v0.2",
            "metadata_assembler": "QuestionBankMetadataAssemblerV2",
            "thinking": {"type": "disabled"},
        },
        "evaluator": dict(evaluator),
        "gate_evidence": {
            "candidate_real_safe": "15/15",
            "candidate_average_output_tokens": _round(
                token["candidate_average_output_tokens"]
            ),
            "paired_output_token_reduction": _round(
                token["paired_output_token_reduction"]
            ),
            "candidate_latency_ms": candidate["latency_ms"],
            "candidate_metadata_fit_mean": _round(
                quality["candidate"]["metadata_fit_mean"]
            ),
            "candidate_text_quality_mean": _round(
                quality["candidate"]["text_quality_mean"]
            ),
            "candidate_minus_baseline_text_quality": _round(
                quality["candidate_minus_baseline_text_quality"]
            ),
            "failed_required_gates": [
                name
                for name, gate in report["thresholds"]["gates"].items()
                if gate["status"] == "fail"
            ],
        },
        "decision_basis": (
            "Protocol v3 passed its operational, Token, latency, safety, and metadata-fit "
            "gates, but failed both required text-quality gates. Under the preregistered "
            "any-required-gate failure rule, thinking.type=disabled is rejected."
        ),
        "next_state": "await_phase_2_4d_e_a_offline_protocol_implementation_authorization",
    }


def build_quality_regression(
    rows: list[dict[str, Any]],
    report: Mapping[str, Any],
    evaluator: Mapping[str, Any],
) -> dict[str, Any]:
    baseline = _variant_summary(rows, "baseline")
    candidate = _variant_summary(rows, "candidate")
    pairs, outcomes = _pairwise(rows)
    return {
        "record_type": "phase_2_4d_d_b_quality_regression_analysis",
        "analysis_version": ANALYSIS_VERSION,
        "protocol": PROTOCOL_VERSION,
        "analysis_type": "unblinded_post_finalize",
        "evaluator": dict(evaluator),
        "overall": {
            "baseline": baseline,
            "candidate": candidate,
            "candidate_minus_baseline": {
                "text_quality": _round(
                    candidate["text_quality_mean"] - baseline["text_quality_mean"]
                ),
                "metadata_fit": _round(
                    candidate["metadata_fit"]["mean"]
                    - baseline["metadata_fit"]["mean"]
                ),
                "mean_question_characters": _round(
                    candidate["mean_question_characters"]
                    - baseline["mean_question_characters"]
                ),
                "text_dimensions": {
                    dimension: _round(
                        candidate["text_dimensions"][dimension]
                        - baseline["text_dimensions"][dimension]
                    )
                    for dimension in TEXT_DIMENSIONS
                },
            },
        },
        "five_text_dimensions": {
            dimension: {
                "baseline_mean": baseline["text_dimensions"][dimension],
                "candidate_mean": candidate["text_dimensions"][dimension],
                "candidate_minus_baseline": _round(
                    _avg(
                        [
                            row["text_scores"][dimension]
                            for row in rows
                            if row["variant"] == "candidate"
                        ]
                    )
                    - _avg(
                        [
                            row["text_scores"][dimension]
                            for row in rows
                            if row["variant"] == "baseline"
                        ]
                    )
                ),
            }
            for dimension in TEXT_DIMENSIONS
        },
        "by_stack": _by_stack(rows),
        "paired_text_quality": {"overall": outcomes, "pairs": pairs},
        "by_module": _by_module(rows),
        "length_score_correlations": _correlations(rows),
        "metadata_fit_distribution": {
            "baseline": baseline["metadata_fit"],
            "candidate": candidate["metadata_fit"],
        },
        "baseline_timeout_retry": _timeout_record(rows, report),
        "limits": [
            "Text-dimension scores are bank-level and cannot be validly assigned to individual modules.",
            "Module analysis therefore uses question-level length and metadata-fit scores.",
            "Observed correlations are descriptive and do not establish causation.",
        ],
    }


def build_next_recommendation() -> dict[str, Any]:
    common = (
        "Prompt v0.2, QuestionBankMetadataAssemblerV2, QuestionDraftBank and final "
        "QuestionBank schemas, deepseek-v4-pro, temperature, max_tokens, retry, fallback, "
        "deadline, fixtures, safety checks, count/order rules, and API contract remain fixed."
    )
    return {
        "record_type": "phase_2_4d_d_b_next_single_variable_recommendation",
        "analysis_version": ANALYSIS_VERSION,
        "recommendation_status": "proposed_only",
        "implemented": False,
        "provider_accessed": False,
        "selected_option": "reasoning_effort_low",
        "priority_reason": (
            "Keeping thinking enabled preserves the condition associated with the stronger "
            "v3 baseline quality, while changing only reasoning_effort directly targets the "
            "reasoning budget that non-thinking removed too aggressively. A fresh high-versus-low "
            "comparison can test Token and latency savings without changing Prompt, model, or output processing."
        ),
        "options": [
            {
                "option": "reasoning_effort_low",
                "disposition": "recommended_next",
                "benefit": "Directly tests a bounded reasoning-intensity control while retaining thinking.",
                "risks": [
                    "Provider and SDK support must be proven at the request boundary.",
                    "Quality may still decline and all existing quality and safety gates remain binding.",
                ],
            },
            {
                "option": "modify_prompt",
                "disposition": "defer",
                "benefit": "Could explicitly restore personalization and training value.",
                "risks": [
                    "Introduces a content-instruction variable rather than isolating reasoning intensity.",
                    "Prior Prompt-only evidence did not produce the required Token reduction.",
                ],
            },
            {
                "option": "deterministic_expansion",
                "disposition": "defer",
                "benefit": "Could add structured detail after generation with deterministic rules.",
                "risks": [
                    "May not reduce Provider output tokens.",
                    "Adds a transformation surface for repetition, evidence drift, and API-content changes.",
                ],
            },
            {
                "option": "relax_quality_threshold",
                "disposition": "prohibited",
                "benefit": None,
                "risks": [
                    "Would rewrite the preregistered acceptance rule after observing a failure.",
                    "Would conceal a 0.6 mean decline and 13 losses across 15 paired comparisons.",
                ],
            },
        ],
        "proposed_new_protocol": {
            "working_name": "phase-2.4d-question-draft-reasoning-effort-token-v4",
            "single_variable": "reasoning_effort",
            "baseline": {
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
            },
            "candidate": {
                "thinking": {"type": "enabled"},
                "reasoning_effort": "low",
            },
            "common_frozen_conditions": common,
            "reuse_protocol_v3_data": False,
            "rerun_both_arms_from_zero": True,
            "new_readiness_required": True,
            "new_protocol_and_preregistration_required": True,
            "implementation_authorized_in_this_phase": False,
            "real_provider_execution_authorized_in_this_phase": False,
        },
        "quality_threshold_policy": "unchanged_and_binding",
        "next_state": "await_phase_2_4d_e_a_offline_protocol_implementation_authorization",
    }


def build_analysis(
    *,
    ab1_dir: Path = DEFAULT_AB1_DIR,
    readiness_ledger: Path = DEFAULT_READINESS_LEDGER,
) -> dict[str, Any]:
    source_paths = _paths(ab1_dir, readiness_ledger)
    hashes_before = _source_hashes(source_paths)
    readiness = _read_object(readiness_ledger)
    manifest = _read_object(source_paths["manifest"])
    report = _read_object(source_paths["final_report_json"])
    private_map = _read_object(source_paths["private_blinding_map"])
    review = _read_object(source_paths["completed_review"])
    _validate_finalized_source(
        readiness=readiness,
        manifest=manifest,
        report=report,
        review=review,
        completed_review_sha256=hashes_before["completed_review"],
    )
    rows = _index_rows(manifest, private_map, review)
    evaluator = review["evaluator"]
    decision = build_final_decision(report, evaluator)
    regression = build_quality_regression(rows, report, evaluator)
    recommendation = build_next_recommendation()
    hashes_after = _source_hashes(source_paths)
    if hashes_after != hashes_before:
        raise QuestionDraftReasoningFinalAnalysisError(
            "Frozen v3 evidence changed during offline analysis"
        )
    return {
        "record_type": "phase_2_4d_d_b_machine_readable_analysis",
        "analysis_version": ANALYSIS_VERSION,
        "generated_on": "2026-10-23",
        "mode": "offline_only",
        "network_accessed": False,
        "provider_calls": 0,
        "source_integrity": {
            "status": "passed",
            "unchanged_during_analysis": True,
            "frozen_asset_count": len(source_paths),
            "sha256": hashes_before,
        },
        "final_decision_record": decision,
        "quality_regression_analysis": regression,
        "next_single_variable_recommendation": recommendation,
    }


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _overlaps(left: Path, right: Path) -> bool:
    left, right = left.resolve(), right.resolve()
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def write_analysis_artifacts(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    ab1_dir: Path = DEFAULT_AB1_DIR,
    readiness_ledger: Path = DEFAULT_READINESS_LEDGER,
) -> dict[str, Path]:
    if _overlaps(output_dir, ab1_dir) or _overlaps(output_dir, readiness_ledger.parent):
        raise QuestionDraftReasoningFinalAnalysisError(
            "Analysis output must not overlap frozen readiness or A/B evidence"
        )
    analysis = build_analysis(ab1_dir=ab1_dir, readiness_ledger=readiness_ledger)
    values = {
        "final-decision-record.json": analysis["final_decision_record"],
        "quality-regression-analysis.json": analysis["quality_regression_analysis"],
        "next-single-variable-recommendation.json": analysis[
            "next_single_variable_recommendation"
        ],
        "phase-2.4d-d-b-analysis.json": analysis,
    }
    paths = {name: output_dir / name for name in values}
    for name, value in values.items():
        _write_json(paths[name], value)
    return paths

