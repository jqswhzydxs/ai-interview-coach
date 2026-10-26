import json

import pytest

from app.services.question_draft_reasoning_protocol_v3 import (
    PROTOCOL_VERSION,
    ProviderCallBudgetV3,
    ProviderReadinessGateV3,
    QuestionDraftReasoningProtocolV3Error,
    account_execution_v3,
    assess_pair_comparability_v3,
    protocol_v3_snapshot,
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
    return account_execution_v3(
        attempts,
        final_execution_mode=mode,
        final_output_safe_valid=safe,
        provider_call_limit=limit,
    )


def test_v3_snapshot_freezes_exact_single_variable():
    snapshot = protocol_v3_snapshot()
    assert snapshot["protocol_version"] == PROTOCOL_VERSION
    assert snapshot["unique_variable"] == "thinking.type"
    assert snapshot["baseline"] == {
        "prompt": "question_bank_draft_agent_v0.2",
        "thinking": {"type": "enabled"},
    }
    assert snapshot["candidate"] == {
        "prompt": "question_bank_draft_agent_v0.2",
        "thinking": {"type": "disabled"},
    }
    assert snapshot["reasoning_effort"] == "absent"
    assert snapshot["per_request_max_tokens"] is None


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
    comparison = assess_pair_comparability_v3(real, fallback)
    assert comparison["status"] == "excluded"
    assert "candidate_final_output_not_real" in comparison["reasons"]
    assert fallback["known_token_lower_bound"]["total_tokens"] is None


def test_call_budget_and_readiness_gate_are_hard_and_separate(tmp_path):
    budget = ProviderCallBudgetV3(limit=1)
    assert budget.consume() == 1
    with pytest.raises(QuestionDraftReasoningProtocolV3Error, match="exhausted"):
        budget.consume()

    gate = ProviderReadinessGateV3(
        ledger_path=tmp_path / "readiness-v3.json",
        provider="deepseek",
        model="deepseek-v4-pro",
        frozen_assets_sha256="a" * 64,
    )
    failed = account([attempt(1, "failed")], mode=None, safe=False, limit=1)
    assert gate.record_attempt(failed) == "pending"
    assert gate.record_attempt(failed) == "blocked"
    with pytest.raises(QuestionDraftReasoningProtocolV3Error, match="terminal"):
        gate.record_attempt(failed)
    assert json.loads(gate.ledger_path.read_text(encoding="utf-8"))["status"] == "blocked"
