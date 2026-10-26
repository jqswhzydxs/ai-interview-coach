import hashlib
import json
from pathlib import Path

import pytest

from app.agents.question_bank_agent import QuestionBankAgent
from app.services import prep_package_service
from app.services.phase_2_4d_b_protocol_review import verify_protected_assets
from app.services.question_draft_token_futility_analysis import (
    DEFAULT_AB1_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_READINESS_LEDGER,
    QuestionDraftTokenFutilityAnalysisError,
    build_early_stop_decision,
    build_next_experiment_options,
    build_pilot_analysis,
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


def test_pilot_pair_analysis_matches_frozen_ab1_without_mutating_sources(tmp_path):
    before_ab1 = _tree_hashes(DEFAULT_AB1_DIR)
    before_readiness = hashlib.sha256(DEFAULT_READINESS_LEDGER.read_bytes()).hexdigest()
    artifacts = write_analysis_artifacts(tmp_path / "analysis")
    after_ab1 = _tree_hashes(DEFAULT_AB1_DIR)
    after_readiness = hashlib.sha256(DEFAULT_READINESS_LEDGER.read_bytes()).hexdigest()
    assert after_ab1 == before_ab1
    assert after_readiness == before_readiness

    analysis = json.loads(
        artifacts["pilot-futility-analysis.json"].read_text(encoding="utf-8")
    )
    assert len(analysis["per_pair"]) == 3
    assert analysis["aggregate"]["baseline"]["output_tokens"] == 9271
    assert analysis["aggregate"]["candidate"]["output_tokens"] == 10197
    assert analysis["aggregate"]["baseline"]["average_output_tokens_per_run"] == pytest.approx(3090.3333333333335)
    assert analysis["aggregate"]["candidate"]["average_output_tokens_per_run"] == 3399
    assert analysis["aggregate"]["baseline"]["average_visible_characters_per_question"] == 139.04
    assert analysis["aggregate"]["candidate"]["average_visible_characters_per_question"] == 57.88
    decoupling = analysis["token_character_decoupling"]
    assert decoupling["candidate_output_token_change_fraction"] == pytest.approx(0.0998813504476324)
    assert decoupling["candidate_visible_character_change_fraction"] == pytest.approx(-0.583716915995397)
    assert decoupling["output_token_density_multiplier"] == pytest.approx(2.6421475978963165)


def test_pair_table_preserves_success_usage_and_billing_distinction():
    analysis = build_pilot_analysis()
    java = next(row for row in analysis["per_pair"] if row["case_id"] == "backend_java_case")
    candidate = java["candidate"]
    assert candidate["successful_response_usage"] == {
        "input_tokens": 1017,
        "output_tokens": 3331,
        "total_tokens": 4348,
    }
    assert candidate["provider_calls"] == 2
    assert candidate["retry_count"] == 1
    assert candidate["billing_usage_completeness"]["status"] == "incomplete"
    assert candidate["billing_usage_completeness"]["unknown_attempts"] == [1]
    assert candidate["execution_reliability"]["timeout_attempts"] == 1
    assert candidate["execution_reliability"]["fallback_used"] is False


def test_early_stop_is_engineering_decision_and_final_gates_stay_not_evaluable():
    decision = build_early_stop_decision(build_pilot_analysis())
    assert decision["decision_status"] == "stopped_for_engineering_futility"
    assert decision["formal_final_gate_status"] == "not_evaluable"
    assert decision["formal_statistical_rejection"] is False
    assert decision["prompt_v0_2_promoted"] is False
    assert decision["full_executed"] is False
    assert decision["blind_review_executed"] is False
    assert decision["finalize_executed"] is False


def test_next_experiment_is_new_protocol_and_does_not_mix_current_data():
    options = build_next_experiment_options()
    assert options["current_data_mixing_allowed"] is False
    assert options["prompt_v0_3_created"] is False
    assert options["recommendation"]["option_id"] == "same_model_reasoning_disabled_or_bounded"
    assert "Rerun both arms from zero" in options["recommendation"]["design"]


def test_analysis_refuses_output_inside_frozen_evidence():
    with pytest.raises(QuestionDraftTokenFutilityAnalysisError, match="must not overlap"):
        write_analysis_artifacts(DEFAULT_AB1_DIR / "forbidden-analysis")


def test_all_prechange_protected_assets_are_byte_identical_and_production_is_unchanged():
    result = verify_protected_assets(PROTECTED_BASELINE)
    assert result["status"] == "passed"
    assert result["checked_file_count"] == 145
    assert result["missing"] == []
    assert result["changed"] == []
    assert prep_package_service.QuestionBankAgent is QuestionBankAgent
    assert QuestionBankAgent.prompt_version == "question_bank_agent_v0.1"
