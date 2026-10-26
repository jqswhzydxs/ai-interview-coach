import json

import pytest

from app.services.question_draft_reasoning_effort_protocol_v4 import (
    PROTOCOL_VERSION,
    ProviderCallBudgetV4,
    ProviderReadinessGateV4,
    QuestionDraftReasoningProtocolV4Error,
    account_execution_v4,
    assess_pair_comparability_v4,
    preregistration_v4_snapshot,
    protocol_v4_snapshot,
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
    return account_execution_v4(
        attempts,
        final_execution_mode=mode,
        final_output_safe_valid=safe,
        provider_call_limit=limit,
    )


def test_v4_snapshot_freezes_exact_single_variable():
    snapshot = protocol_v4_snapshot()
    assert snapshot["protocol_version"] == PROTOCOL_VERSION
    assert snapshot["unique_variable"] == "reasoning_effort"
    assert snapshot["baseline"] == {
        "prompt": "question_bank_draft_agent_v0.2",
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    }
    assert snapshot["candidate"] == {
        "prompt": "question_bank_draft_agent_v0.2",
        "thinking": {"type": "enabled"},
        "reasoning_effort": "low",
    }
    assert snapshot["reasoning_effort_is_explicit_in_both_arms"] is True
    assert snapshot["thinking_is_explicit_and_fixed"] == {"type": "enabled"}
    assert snapshot["historical_v3_samples_reused"] is False
    assert snapshot["per_request_max_tokens"] is None


def test_machine_preregistration_freezes_stages_gates_privacy_and_no_v3_reuse():
    preregistration = preregistration_v4_snapshot()
    assert preregistration["status"] == "frozen_offline_before_real_data"
    assert preregistration["design"]["historical_v3_samples_reused"] is False
    assert preregistration["design"]["pilot_pairs"] == [1]
    assert preregistration["design"]["full_additional_pairs"] == [2, 3, 4, 5]
    assert preregistration["frozen_generation"]["provider_call_budget"] == 62
    assert preregistration["blind_review"]["text_score_count"] == 150
    assert preregistration["blind_review"]["metadata_score_count"] == 750
    assert preregistration["required_final_gates"]["candidate_text_quality_gte"] == 4.0
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
    comparison = assess_pair_comparability_v4(real, fallback)
    assert comparison["status"] == "excluded"
    assert "candidate_final_output_not_real" in comparison["reasons"]
    assert fallback["known_token_lower_bound"]["total_tokens"] is None


def test_call_budget_and_readiness_gate_are_hard_and_separate(tmp_path):
    budget = ProviderCallBudgetV4(limit=1)
    assert budget.consume() == 1
    with pytest.raises(QuestionDraftReasoningProtocolV4Error, match="exhausted"):
        budget.consume()

    gate = ProviderReadinessGateV4(
        ledger_path=tmp_path / "readiness-v4.json",
        provider="deepseek",
        model="deepseek-v4-pro",
        frozen_assets_sha256="a" * 64,
    )
    failed = account([attempt(1, "failed")], mode=None, safe=False, limit=1)
    assert gate.record_attempt(failed) == "pending"
    assert gate.record_attempt(failed) == "blocked"
    with pytest.raises(QuestionDraftReasoningProtocolV4Error, match="terminal"):
        gate.record_attempt(failed)
    assert json.loads(gate.ledger_path.read_text(encoding="utf-8"))["status"] == "blocked"
