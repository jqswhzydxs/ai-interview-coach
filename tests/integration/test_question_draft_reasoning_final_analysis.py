import hashlib
import json
from pathlib import Path

import pytest

from app.agents.question_bank_agent import QuestionBankAgent
from app.services import prep_package_service
from app.services.phase_2_4d_b_protocol_review import verify_protected_assets
from app.services.question_draft_reasoning_final_analysis import (
    DEFAULT_AB1_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_READINESS_LEDGER,
    QuestionDraftReasoningFinalAnalysisError,
    build_analysis,
    write_analysis_artifacts,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTECTED_BASELINE = DEFAULT_OUTPUT_DIR / "protected-assets-before.json"


def _tree_hashes(path: Path) -> dict[str, str]:
    return {
        item.relative_to(path).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in path.rglob("*")
        if item.is_file()
    }


def test_final_analysis_matches_frozen_v3_and_does_not_mutate_sources(tmp_path):
    before_ab1 = _tree_hashes(DEFAULT_AB1_DIR)
    before_readiness = hashlib.sha256(DEFAULT_READINESS_LEDGER.read_bytes()).hexdigest()
    artifacts = write_analysis_artifacts(tmp_path / "analysis")
    assert _tree_hashes(DEFAULT_AB1_DIR) == before_ab1
    assert hashlib.sha256(DEFAULT_READINESS_LEDGER.read_bytes()).hexdigest() == before_readiness

    analysis = json.loads(
        artifacts["phase-2.4d-d-b-analysis.json"].read_text(encoding="utf-8")
    )
    decision = analysis["final_decision_record"]
    assert decision["final_decision"] == "fail"
    assert decision["candidate_promotion"] == "denied"
    assert decision["production_integration"] is False
    assert decision["frontend_stage_entered"] is False
    assert decision["evaluator"]["type"] == "AI"
    assert decision["gate_evidence"]["candidate_average_output_tokens"] == pytest.approx(680.533333)
    assert decision["gate_evidence"]["paired_output_token_reduction"] == pytest.approx(0.815009)


def test_five_dimensions_and_paired_regression_are_unblinded_correctly():
    quality = build_analysis()["quality_regression_analysis"]
    expected = {
        "personalization": (4.066667, 3.2, -0.866667),
        "technical_correctness_and_stack_boundary": (4.2, 3.8, -0.4),
        "coverage_and_substantive_diversity": (4.466667, 3.933333, -0.533333),
        "interview_training_value": (4.6, 3.8, -0.8),
        "clarity": (4.533333, 4.133333, -0.4),
    }
    for dimension, values in expected.items():
        actual = quality["five_text_dimensions"][dimension]
        assert actual["baseline_mean"] == pytest.approx(values[0])
        assert actual["candidate_mean"] == pytest.approx(values[1])
        assert actual["candidate_minus_baseline"] == pytest.approx(values[2])
    assert quality["paired_text_quality"]["overall"] == {
        "win": 1,
        "tie": 1,
        "loss": 13,
    }
    assert len(quality["paired_text_quality"]["pairs"]) == 15


def test_stack_module_metadata_and_correlation_analysis_are_complete():
    quality = build_analysis()["quality_regression_analysis"]
    assert set(quality["by_stack"]) == {"Go", "Java", "Python"}
    assert quality["by_stack"]["Go"]["paired_text_quality"] == {
        "win": 1,
        "tie": 0,
        "loss": 4,
    }
    assert quality["by_stack"]["Java"]["paired_text_quality"] == {
        "win": 0,
        "tie": 0,
        "loss": 5,
    }
    assert quality["by_stack"]["Python"]["paired_text_quality"] == {
        "win": 0,
        "tie": 1,
        "loss": 4,
    }
    expected_counts = {"self_intro": 120, "professional": 120, "behavior_project": 135}
    for module, count in expected_counts.items():
        assert quality["by_module"][module]["baseline"]["question_count"] == count
        assert quality["by_module"][module]["candidate"]["question_count"] == count
    assert quality["metadata_fit_distribution"]["candidate"]["count"] == 375
    assert quality["metadata_fit_distribution"]["candidate"]["mean"] == pytest.approx(3.816)
    assert quality["length_score_correlations"]["bank_mean_question_characters_vs_text_quality"]["all"]["sample_count"] == 30
    assert "do not establish" in quality["length_score_correlations"]["interpretation"]


def test_baseline_timeout_keeps_success_usage_comparable_and_billing_as_lower_bound():
    timeout = build_analysis()["quality_regression_analysis"]["baseline_timeout_retry"]
    assert timeout["variant"] == "baseline"
    assert timeout["provider_calls"] == 2
    assert timeout["retry_count"] == 1
    assert timeout["failed_attempt_usage"] == "unknown"
    assert timeout["successful_response_usage_complete"] is True
    assert timeout["successful_response_usage"]["output_tokens"] == 3785
    assert timeout["billing_usage_completeness"]["status"] == "incomplete"
    assert timeout["billing_total_interpretation"] == "lower_bound_only"
    assert timeout["successful_response_token_pair_comparable"] is True
    assert timeout["effect_on_registered_successful_response_token_conclusion"] == "none"


def test_next_recommendation_is_strict_single_variable_and_does_not_relax_quality():
    recommendation = build_analysis()["next_single_variable_recommendation"]
    proposed = recommendation["proposed_new_protocol"]
    assert recommendation["selected_option"] == "reasoning_effort_low"
    assert recommendation["quality_threshold_policy"] == "unchanged_and_binding"
    assert proposed["single_variable"] == "reasoning_effort"
    assert proposed["baseline"] == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    }
    assert proposed["candidate"] == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "low",
    }
    assert proposed["reuse_protocol_v3_data"] is False
    assert proposed["rerun_both_arms_from_zero"] is True
    assert recommendation["implemented"] is False
    relax = next(row for row in recommendation["options"] if row["option"] == "relax_quality_threshold")
    assert relax["disposition"] == "prohibited"


def test_analysis_output_is_sanitized_idempotent_and_separate(tmp_path):
    output = tmp_path / "analysis"
    first = write_analysis_artifacts(output)
    first_hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in first.items()}
    second = write_analysis_artifacts(output)
    second_hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in second.items()}
    assert first_hashes == second_hashes
    serialized = first["phase-2.4d-d-b-analysis.json"].read_text(encoding="utf-8")
    for prohibited in ("question_text", "evidence_context", "reasoning_content", "api_key", "raw_response"):
        assert prohibited not in serialized
    with pytest.raises(QuestionDraftReasoningFinalAnalysisError, match="must not overlap"):
        write_analysis_artifacts(DEFAULT_AB1_DIR / "forbidden")
    with pytest.raises(QuestionDraftReasoningFinalAnalysisError, match="must not overlap"):
        write_analysis_artifacts(DEFAULT_READINESS_LEDGER.parent / "forbidden")


def test_prechange_assets_and_production_default_remain_unchanged():
    result = verify_protected_assets(PROTECTED_BASELINE)
    assert result["status"] == "passed"
    assert result["checked_file_count"] == 189
    assert result["missing"] == []
    assert result["changed"] == []
    assert prep_package_service.QuestionBankAgent is QuestionBankAgent
    assert QuestionBankAgent.prompt_version == "question_bank_agent_v0.1"
