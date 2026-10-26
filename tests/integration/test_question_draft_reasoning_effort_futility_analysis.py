from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.services.question_draft_reasoning_effort_futility_analysis import (
    QuestionDraftReasoningEffortFutilityError,
    analyze_v4_pilot,
    file_sha256,
    write_analysis_artifacts,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = (
    PROJECT_ROOT
    / "storage/reports/question-bank-token-phase-2-4d-e-v4-20261024-ab1"
)
REPORT = RUN_DIR / "question-draft-reasoning-effort-v4-report.json"
AUDIT = RUN_DIR / "audit/executions.json"
PROTECTED = (
    PROJECT_ROOT
    / "storage/reports/question-bank-token-phase-2-4d-e-b-offline-20261024"
    / "protected-assets-before.json"
)


def test_actual_pilot_analysis_matches_frozen_evidence_and_does_not_mutate_sources():
    before = (file_sha256(REPORT), file_sha256(AUDIT))
    artifacts = analyze_v4_pilot(REPORT, AUDIT)
    after = (file_sha256(REPORT), file_sha256(AUDIT))

    assert before == after
    analysis = artifacts.analysis
    assert analysis["gate_interpretation"] == {
        "pilot_execution_gate": "passed",
        "formal_full_gates": "not_evaluable",
        "formal_token_gate": "not_evaluable",
        "comparable_pairs": 3,
        "required_comparable_pairs": 12,
        "formal_statistical_rejection": False,
    }
    token = analysis["descriptive_token_result"]
    assert token["baseline_high_output_tokens_total"] == 16211
    assert token["candidate_low_output_tokens_total"] == 14250
    assert token["candidate_low_output_tokens_mean"] == 4750
    assert token["paired_output_token_reduction"] == pytest.approx(0.1209672444636358)
    feasibility = analysis["absolute_target_feasibility"]
    assert feasibility["required_remaining_mean_output_tokens_lte"] == 1062.5
    assert feasibility["pilot_candidate_min_output_tokens"] == 2171
    assert feasibility["mathematical_impossibility_claimed"] is False


def test_pair_analysis_preserves_unknown_visible_usage_and_retry_lower_bound():
    analysis = analyze_v4_pilot(REPORT, AUDIT).analysis
    go = next(row for row in analysis["pairs"] if row["technology_stack"] == "Go")
    candidate = go["candidate_low"]

    assert candidate["retry_count"] == 1
    assert candidate["provider_calls"] == 2
    assert candidate["billing_usage_completeness"]["status"] == "incomplete"
    assert candidate["failed_attempts"] == [
        {
            "failure_category": "network",
            "exception_type": "ConnectError",
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "usage_status": "not_available",
        }
    ]
    assert candidate["visible_completion_tokens"] == {
        "status": "unknown",
        "value": None,
    }
    assert analysis["usage_policy"]["output_minus_reasoning_derivation_used"] is False
    assert analysis["usage_policy"]["missing_fields_imputed_as_zero"] is False


def test_analysis_captures_reasoning_variability_lengths_and_stack_differences():
    analysis = analyze_v4_pilot(REPORT, AUDIT).analysis
    assert analysis["reasoning_variability"]["baseline_high_total"] == 13888
    assert analysis["reasoning_variability"]["candidate_low_total"] == 12025
    distribution = analysis["reasoning_variability"]["candidate_low_distribution"]
    assert distribution["min"] == 1457
    assert distribution["max"] == 6674
    assert distribution["range"] == 5217
    visible = analysis["visible_question_length"]
    assert visible["candidate_average_characters"] == pytest.approx(98.2266666667)
    assert visible["candidate_above_module_recommended"] == 38
    assert visible["token_proxy"] is False
    assert visible["quality_proxy"] is False
    assert {row["technology_stack"] for row in analysis["pairs"]} == {
        "Go",
        "Java",
        "Python",
    }


def test_decision_and_recommendation_use_required_non_statistical_language():
    artifacts = analyze_v4_pilot(REPORT, AUDIT)
    decision = artifacts.decision
    assert decision["status"] == "stopped_for_engineering_futility"
    assert decision["pilot_execution_gate"] == "passed"
    assert decision["formal_full_gates"] == "not_evaluable"
    assert decision["formal_statistical_rejection"] is False
    assert not any(
        decision["actions"][key]
        for key in (
            "run_full",
            "generate_blind_review",
            "execute_finalize",
            "promote_low_effort_candidate",
            "modify_original_v4_assets",
            "production_default_changed",
        )
    )

    recommendation = artifacts.recommendation
    design = recommendation["proposed_design_only"]
    assert recommendation["strict_single_variable"] == "prompt_text"
    assert design["baseline"]["thinking"] == {"type": "disabled"}
    assert design["candidate"]["thinking"] == {"type": "disabled"}
    assert design["baseline"]["prompt"].endswith("v0.2")
    assert design["candidate"]["prompt"].endswith("v0.3")
    assert design["both_arms_fully_rerun"] is True
    assert design["reuse_v3_samples"] is False
    assert design["reuse_v4_samples"] is False
    assert recommendation["implementation_status"] == {
        "prompt_v0_3_created": False,
        "new_runner_created": False,
        "real_experiment_started": False,
    }
    assert all(recommendation["prohibitions"].values())


def test_writer_targets_only_the_supplied_offline_directory(tmp_path):
    source_before = (file_sha256(REPORT), file_sha256(AUDIT))
    artifacts = analyze_v4_pilot(REPORT, AUDIT)
    written = write_analysis_artifacts(artifacts, tmp_path / "offline")

    assert set(written) == {
        "pilot-futility-analysis.json",
        "early-stop-decision.json",
        "next-single-variable-recommendation.json",
    }
    assert all(path.is_file() for path in written.values())
    assert (file_sha256(REPORT), file_sha256(AUDIT)) == source_before


def test_wrong_status_and_completed_full_are_rejected(tmp_path):
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    audit_copy = tmp_path / "audit.json"
    audit_copy.write_bytes(AUDIT.read_bytes())

    for status, completion in (("prepared", "not_started"), ("pilot_passed", "completed")):
        candidate = copy.deepcopy(report)
        candidate["status"] = status
        candidate["completion_status"] = completion
        path = tmp_path / f"{status}-{completion}.json"
        path.write_text(json.dumps(candidate), encoding="utf-8")
        with pytest.raises(QuestionDraftReasoningEffortFutilityError):
            analyze_v4_pilot(path, audit_copy)


def test_all_56_protected_assets_remain_unchanged():
    baseline = json.loads(PROTECTED.read_text(encoding="utf-8"))
    assert baseline["file_count"] == 56
    for relative_path, expected in baseline["files"].items():
        path = PROJECT_ROOT / relative_path
        assert path.is_file(), relative_path
        assert file_sha256(path) == expected, relative_path

