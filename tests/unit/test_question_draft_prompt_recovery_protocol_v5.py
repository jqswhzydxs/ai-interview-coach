import json

import pytest

from app.services.question_draft_prompt_recovery_protocol_v5 import (
    PROTOCOL_VERSION,
    ProviderCallBudgetV5,
    ProviderReadinessGateV5,
    QuestionDraftPromptRecoveryProtocolV5Error,
    account_execution_v5,
    assess_pair_comparability_v5,
    preregistration_v5_snapshot,
    prompt_recovery_protocol_v5_snapshot,
)


def attempt(number, status, usage=None, **extra):
    return {
        "call": number,
        "status": status,
        "token_usage": usage
        or {"input_tokens": None, "output_tokens": None, "total_tokens": None},
        **extra,
    }


def account(attempts, *, mode="real", safe=True, limit=10):
    return account_execution_v5(
        attempts,
        final_execution_mode=mode,
        final_output_safe_valid=safe,
        provider_call_limit=limit,
    )


def test_v5_snapshot_freezes_exact_single_variable():
    snapshot = prompt_recovery_protocol_v5_snapshot()
    assert snapshot["protocol_version"] == PROTOCOL_VERSION
    assert snapshot["unique_variable"] == "prompt_asset"
    assert snapshot["baseline"] == {
        "prompt": "question_bank_draft_agent_v0.2",
        "thinking": {"type": "disabled"},
    }
    assert snapshot["candidate"] == {
        "prompt": "question_bank_draft_agent_v0.3",
        "thinking": {"type": "disabled"},
    }
    assert snapshot["reasoning_effort"] == "absent_in_both_arms"
    assert snapshot["thinking_is_explicit_and_fixed"] == {"type": "disabled"}
    assert snapshot["historical_v3_samples_reused"] is False
    assert snapshot["per_request_max_tokens"] is None


def test_machine_preregistration_freezes_stages_gates_privacy_and_no_v3_reuse():
    preregistration = preregistration_v5_snapshot()
    assert preregistration["status"] == "frozen_offline_before_real_data"
    assert preregistration["design"]["historical_v3_samples_reused"] is False
    assert preregistration["design"]["historical_v4_samples_reused"] is False
    assert preregistration["design"]["pilot_pairs"] == [1]
    assert preregistration["design"]["full_additional_pairs"] == [2, 3, 4, 5]
    assert preregistration["frozen_generation"]["provider_call_budget"] == 62
    assert preregistration["blind_review"]["text_score_count"] == 150
    assert preregistration["blind_review"]["metadata_score_count"] == 750
    assert preregistration["required_final_gates"]["candidate_text_quality_gte"] == 4.0
    assert preregistration["required_final_gates"]["candidate_minus_baseline_text_quality_gte"] == 0.2
    assert preregistration["required_final_gates"]["paired_output_token_change_reported"] is True
    assert "paired_output_token_reduction_gte" not in preregistration["required_final_gates"]
    assert preregistration["quality_thresholds_relaxed"] is False
    assert preregistration["privacy"]["persist_chain_of_thought"] is False


def test_timeout_then_success_keeps_success_usage_and_incomplete_billing():
    result = account(
        [
            attempt(1, "failed", failure_category="read_timeout"),
            attempt(
                2,
                "succeeded",
                {"input_tokens": 100, "output_tokens": 200, "total_tokens": 300},
            ),
        ]
    )
    assert result["successful_response_usage"]["output_tokens"] == 200
    assert result["billing_usage_completeness"]["status"] == "incomplete"
    assert result["known_token_lower_bound"]["total_tokens"] == 300
    assert result["known_token_lower_bound"]["is_complete_total"] is False
    assert result["execution_reliability"]["timeout_attempts"] == 1


def test_fallback_and_unknown_usage_are_excluded_from_pair_comparison():
    real = account(
        [attempt(1, "succeeded", {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30})]
    )
    fallback = account([attempt(1, "failed")], mode="fallback", safe=False)
    comparison = assess_pair_comparability_v5(real, fallback)
    assert comparison["status"] == "excluded"
    assert "candidate_final_output_not_real" in comparison["reasons"]
    assert fallback["known_token_lower_bound"]["total_tokens"] is None


def test_call_budget_and_readiness_gate_are_hard_and_separate(tmp_path):
    budget = ProviderCallBudgetV5(limit=1)
    assert budget.consume() == 1
    with pytest.raises(QuestionDraftPromptRecoveryProtocolV5Error, match="exhausted"):
        budget.consume()

    gate = ProviderReadinessGateV5(
        ledger_path=tmp_path / "readiness-v5.json",
        provider="deepseek",
        model="deepseek-v4-pro",
        frozen_assets_sha256="a" * 64,
    )
    failed = account([attempt(1, "failed")], mode=None, safe=False, limit=1)
    assert gate.record_attempt(failed) == "pending"
    assert gate.record_attempt(failed) == "blocked"
    with pytest.raises(QuestionDraftPromptRecoveryProtocolV5Error, match="terminal"):
        gate.record_attempt(failed)
    assert json.loads(gate.ledger_path.read_text(encoding="utf-8"))["status"] == "blocked"

