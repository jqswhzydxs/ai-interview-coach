import hashlib
import json
from pathlib import Path

import pytest

from app.agents.question_bank_agent import QuestionBankAgent
from app.services import prep_package_service
from app.services.phase_2_4d_b_protocol_review import verify_protected_assets
from app.services.question_draft_prompt_recovery_final_analysis import (
    DEFAULT_AB1_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_READINESS_LEDGER,
    QuestionDraftPromptRecoveryFinalAnalysisError,
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


def test_final_decision_matches_frozen_v5_without_mutating_sources(tmp_path):
    before_ab1 = _tree_hashes(DEFAULT_AB1_DIR)
    before_readiness = hashlib.sha256(DEFAULT_READINESS_LEDGER.read_bytes()).hexdigest()
    artifacts = write_analysis_artifacts(tmp_path / "analysis")
    assert _tree_hashes(DEFAULT_AB1_DIR) == before_ab1
    assert hashlib.sha256(DEFAULT_READINESS_LEDGER.read_bytes()).hexdigest() == before_readiness

    analysis = json.loads(
        artifacts["phase-2.4d-f-b-final-decision.json"].read_text(encoding="utf-8")
    )
    decision = analysis["final_decision_record"]
    assert decision["final_decision"] == "fail"
    assert decision["candidate_promotion"] == "research_candidate_not_promoted"
    assert decision["production_integration"] is False
    assert decision["production_default_question_bank_agent_changed"] is False
    assert decision["post_hoc_threshold_relaxation"] is False
    assert decision["second_review_performed"] is False
    assert decision["same_protocol_rerun_performed"] is False
    assert decision["prompt_v0_4_created"] is False
    assert decision["continuous_prompt_tuning_route"] == "stopped"
    assert decision["evaluator"]["type"] == "AI"
    assert decision["gate_evidence"]["candidate_average_output_tokens"] == 788
    assert decision["gate_evidence"]["candidate_minus_baseline_text_quality"] == pytest.approx(0.173333)
    assert decision["gate_evidence"]["comparable_pairs"] == 15


def test_unblinded_dimensions_stacks_and_pair_outcomes_are_exact():
    attribution = build_analysis()["failure_attribution_report"]
    expected = {
        "personalization": (4.2, 4.466667, 0.266667),
        "technical_correctness_and_stack_boundary": (3.866667, 3.933333, 0.066667),
        "coverage_and_substantive_diversity": (3.733333, 3.866667, 0.133333),
        "interview_training_value": (4.133333, 4.533333, 0.4),
        "clarity": (4.0, 4.0, 0.0),
    }
    for dimension, values in expected.items():
        actual = attribution["five_text_dimensions"][dimension]
        assert actual["baseline_mean"] == pytest.approx(values[0])
        assert actual["candidate_mean"] == pytest.approx(values[1])
        assert actual["candidate_minus_baseline"] == pytest.approx(values[2])
    assert attribution["paired_text_quality"]["overall"] == {
        "win": 10,
        "tie": 3,
        "loss": 2,
    }
    assert len(attribution["paired_text_quality"]["pairs"]) == 15
    assert attribution["by_stack"]["Go"]["paired_text_quality"] == {"win": 3, "tie": 2, "loss": 0}
    assert attribution["by_stack"]["Java"]["paired_text_quality"] == {"win": 3, "tie": 0, "loss": 2}
    assert attribution["by_stack"]["Python"]["paired_text_quality"] == {"win": 4, "tie": 1, "loss": 0}
    java = attribution["by_stack"]["Java"]["candidate"]["text_dimensions"]
    assert java["technical_correctness_and_stack_boundary"] == 3.8
    assert java["coverage_and_substantive_diversity"] == 3.6
    assert attribution["primary_gap"]["stack"] == "Java"
    assert "does not establish" in attribution["primary_gap"]["interpretation"]


def test_metadata_token_latency_length_and_correlations_are_reported_descriptively():
    attribution = build_analysis()["failure_attribution_report"]
    candidate = attribution["overall"]["candidate"]
    assert candidate["metadata_fit"]["mean"] == pytest.approx(3.896)
    assert candidate["output_tokens"]["mean"] == 788
    assert candidate["latency_ms"]["p95"] == 12409
    assert candidate["latency_ms"]["max"] == 12409
    assert candidate["mean_question_characters"] == pytest.approx(38.368)
    assert set(attribution["by_module"]) == {
        "self_intro",
        "professional",
        "behavior_project",
    }
    assert attribution["by_module"]["professional"]["candidate"]["length"]["mean"] == pytest.approx(44.341667)
    assert attribution["metadata_fit_distribution"]["candidate"]["count"] == 375
    interpretation = attribution["length_score_correlations"]["interpretation"]
    assert "do not establish" in interpretation


def test_two_baseline_retries_preserve_success_usage_comparability():
    retries = build_analysis()["failure_attribution_report"]["baseline_retries"]
    by_stack = {row["stack"]: row for row in retries}
    java = by_stack["Java"]
    assert java["pair"] == 3
    assert java["failure_kind"] == "network"
    assert java["failed_attempt_usage"] == "unknown"
    assert java["billing_usage_completeness"]["status"] == "incomplete"
    assert java["billing_total_interpretation"] == "lower_bound_only"
    assert java["successful_response_usage"]["output_tokens"] == 664

    python = by_stack["Python"]
    assert python["pair"] == 3
    assert python["failure_kind"] == "other"
    assert python["failed_attempt_usage"] == {
        "input_tokens": 970,
        "output_tokens": 735,
        "total_tokens": 1705,
    }
    assert python["failed_attempt_usage_enters_known_lower_bound"] is True
    assert python["known_token_lower_bound"]["total_tokens"] == 3388
    assert python["successful_response_usage"]["output_tokens"] == 713
    assert all(row["successful_response_token_pair_comparable"] for row in retries)
    assert all(row["registered_comparable_pair_count"] == 15 for row in retries)


def test_backend_freeze_and_frontend_entry_are_decoupled_from_model_promotion():
    analysis = build_analysis()
    backend = analysis["backend_contract_freeze_readiness"]
    frontend = analysis["frontend_entry_recommendation"]
    assert backend["status"] == "ready_for_phase_2_5_contract_freeze"
    assert set(("source_quality", "score_available", "evaluation_mode", "fallback_reason")).issubset(
        backend["contracts_ready_to_freeze"]
    )
    assert backend["production_agent_switch_permitted"] is False
    assert backend["prompt_v0_3_promotion_assumed"] is False
    assert frontend["recommendation"] == "allow_phase_2_5_frontend_mock_and_api_contract_development"
    assert frontend["requires_next_phase_authorization"] is True
    assert frontend["frontend_must_not_assume_prompt_v0_3_promoted"] is True
    assert frontend["model_research_decoupled_from_frontend"] is True
    assert frontend["degraded_reason_source"] == "structured fallback_reason from the backend run contract"


def test_analysis_output_is_sanitized_idempotent_and_separate(tmp_path):
    output = tmp_path / "analysis"
    first = write_analysis_artifacts(output)
    first_hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in first.items()}
    second = write_analysis_artifacts(output)
    second_hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in second.items()}
    assert first_hashes == second_hashes
    serialized = first["phase-2.4d-f-b-final-decision.json"].read_text(encoding="utf-8")
    for prohibited in ("question_text", "evidence_context", "reasoning_content", "api_key", "raw_response"):
        assert prohibited not in serialized
    with pytest.raises(QuestionDraftPromptRecoveryFinalAnalysisError, match="must not overlap"):
        write_analysis_artifacts(DEFAULT_AB1_DIR / "forbidden")
    with pytest.raises(QuestionDraftPromptRecoveryFinalAnalysisError, match="must not overlap"):
        write_analysis_artifacts(DEFAULT_READINESS_LEDGER.parent / "forbidden")


def test_frozen_assets_and_production_default_remain_unchanged():
    result = verify_protected_assets(PROTECTED_BASELINE)
    assert result["status"] == "passed"
    assert result["checked_file_count"] == 30
    assert result["missing"] == []
    assert result["changed"] == []
    assert prep_package_service.QuestionBankAgent is QuestionBankAgent
    assert QuestionBankAgent.prompt_version == "question_bank_agent_v0.1"
    assert not (PROJECT_ROOT / "app/agents/prompts/question_bank_draft_agent_v0.4.md").exists()
