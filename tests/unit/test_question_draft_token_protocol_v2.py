import json

import pytest

from app.services.question_draft_token_protocol_v2 import (
    PER_REQUEST_MAX_TOKENS,
    PROTOCOL_VERSION,
    READINESS_MAX_ATTEMPTS,
    TOTAL_TOKEN_BUDGET_POLICY,
    ProviderCallBudget,
    ProviderReadinessGate,
    QuestionDraftTokenProtocolV2Error,
    account_execution_v2,
    assess_pair_comparability,
    protocol_v2_snapshot,
)


def attempt(
    number,
    status,
    *,
    usage=None,
    failure_category=None,
    exception_type=None,
):
    return {
        "call": number,
        "status": status,
        "token_usage": usage
        or {"input_tokens": None, "output_tokens": None, "total_tokens": None},
        "failure_category": failure_category,
        "exception_type": exception_type,
    }


def account(attempts, *, mode="real", safe=True, limit=10):
    return account_execution_v2(
        attempts,
        final_execution_mode=mode,
        final_output_safe_valid=safe,
        provider_call_limit=limit,
    )


def test_timeout_then_success_separates_response_usage_from_billing_usage():
    result = account(
        [
            attempt(1, "failed", failure_category="read_timeout"),
            attempt(
                2,
                "succeeded",
                usage={"input_tokens": 100, "output_tokens": 200, "total_tokens": 300},
            ),
        ]
    )
    assert result["successful_response_usage"] == {
        "status": "complete",
        "attempt": 2,
        "input_tokens": 100,
        "output_tokens": 200,
        "total_tokens": 300,
    }
    assert result["billing_usage_completeness"] == {
        "status": "incomplete",
        "is_complete": False,
        "unknown_attempts": [1],
        "known_attempts": [2],
    }
    assert result["known_token_lower_bound"] == {
        "input_tokens": 100,
        "output_tokens": 200,
        "total_tokens": 300,
        "is_complete_total": False,
        "unknown_attempt_count": 1,
    }
    assert result["execution_reliability"]["timeout_attempts"] == 1
    assert result["execution_reliability"]["retry_count"] == 1


def test_network_error_then_success_is_classified_independently():
    result = account(
        [
            attempt(
                1,
                "failed",
                failure_category="network",
                exception_type="RemoteProtocolError",
            ),
            attempt(
                2,
                "succeeded",
                usage={"input_tokens": 40, "output_tokens": 60, "total_tokens": 100},
            ),
        ]
    )
    assert result["execution_reliability"]["network_error_attempts"] == 1
    assert result["successful_response_usage"]["output_tokens"] == 60
    assert result["billing_usage_completeness"]["status"] == "incomplete"


def test_two_network_errors_fallback_keep_unknown_usage_null():
    result = account(
        [
            attempt(1, "failed", failure_category="network", exception_type="RemoteProtocolError"),
            attempt(2, "failed", failure_category="network", exception_type="RemoteProtocolError"),
        ],
        mode="fallback",
        safe=False,
        limit=2,
    )
    assert result["successful_response_usage"]["status"] == "not_applicable"
    assert result["billing_usage_completeness"]["status"] == "incomplete"
    assert result["known_token_lower_bound"]["input_tokens"] is None
    assert result["known_token_lower_bound"]["output_tokens"] is None
    assert result["known_token_lower_bound"]["total_tokens"] is None
    assert result["execution_reliability"]["network_error_attempts"] == 2
    assert result["execution_reliability"]["fallback_used"] is True


def test_known_token_lower_bound_sums_only_observed_values():
    result = account(
        [
            attempt(
                1,
                "failed",
                usage={"input_tokens": 10, "output_tokens": None, "total_tokens": None},
                failure_category="network",
            ),
            attempt(
                2,
                "succeeded",
                usage={"input_tokens": 20, "output_tokens": 30, "total_tokens": 50},
            ),
        ]
    )
    assert result["known_token_lower_bound"] == {
        "input_tokens": 30,
        "output_tokens": 30,
        "total_tokens": 50,
        "is_complete_total": False,
        "unknown_attempt_count": 1,
    }


def test_provider_call_budget_is_a_hard_pre_call_stop():
    budget = ProviderCallBudget(limit=2)
    assert budget.consume() == 1
    assert budget.consume() == 2
    assert budget.snapshot()["exhausted"] is True
    with pytest.raises(QuestionDraftTokenProtocolV2Error, match="exhausted before call"):
        budget.consume()
    with pytest.raises(QuestionDraftTokenProtocolV2Error, match="exceeded"):
        account_execution_v2(
            [attempt(1, "failed"), attempt(2, "failed"), attempt(3, "failed")],
            final_execution_mode="fallback",
            final_output_safe_valid=False,
            provider_call_limit=2,
        )


def test_comparable_pair_uses_success_usage_and_excludes_unsafe_or_unknown():
    baseline = account(
        [attempt(1, "failed", failure_category="read_timeout"), attempt(
            2, "succeeded",
            usage={"input_tokens": 100, "output_tokens": 200, "total_tokens": 300},
        )]
    )
    candidate = account([attempt(
        1, "succeeded",
        usage={"input_tokens": 90, "output_tokens": 150, "total_tokens": 240},
    )])
    comparison = assess_pair_comparability(baseline, candidate)
    assert comparison == {
        "status": "comparable",
        "reasons": [],
        "baseline_output_tokens": 200,
        "candidate_output_tokens": 150,
    }
    # Billing is still prominently incomplete even though successful-response
    # usage makes this pair token-comparable under v2.
    assert baseline["billing_usage_completeness"]["status"] == "incomplete"

    fallback = account([attempt(1, "failed")], mode="fallback", safe=False)
    excluded = assess_pair_comparability(baseline, fallback)
    assert excluded["status"] == "excluded"
    assert "candidate_final_output_not_real" in excluded["reasons"]
    assert "candidate_successful_response_usage_incomplete" in excluded["reasons"]

    unknown_success = account([attempt(
        1,
        "succeeded",
        usage={"input_tokens": 90, "output_tokens": None, "total_tokens": None},
    )])
    assert assess_pair_comparability(baseline, unknown_success)["status"] == "excluded"


def test_readiness_gate_uses_one_ledger_and_blocks_after_two_failures(tmp_path):
    ledger = tmp_path / "provider-readiness-v2.json"
    gate = ProviderReadinessGate(
        ledger_path=ledger,
        provider="offline-test-provider",
        model="frozen-model",
        frozen_assets_sha256="a" * 64,
    )
    failed = account(
        [attempt(1, "failed", failure_category="network")],
        mode="fallback",
        safe=False,
        limit=1,
    )
    assert gate.record_attempt(failed) == "pending"
    with pytest.raises(QuestionDraftTokenProtocolV2Error, match="must not be created"):
        gate.assert_ab_start_allowed()
    assert gate.record_attempt(failed) == "blocked"
    with pytest.raises(QuestionDraftTokenProtocolV2Error, match="terminal"):
        gate.record_attempt(failed)
    reopened = ProviderReadinessGate(
        ledger_path=ledger,
        provider="offline-test-provider",
        model="frozen-model",
        frozen_assets_sha256="a" * 64,
    )
    assert reopened.status == "blocked"
    state = json.loads(ledger.read_text(encoding="utf-8"))
    assert state["max_attempts"] == READINESS_MAX_ATTEMPTS == 2
    assert state["scope"] == "readiness_only_not_token_ab"


def test_readiness_requires_one_clean_real_usage_complete_response(tmp_path):
    gate = ProviderReadinessGate(
        ledger_path=tmp_path / "provider-readiness-v2.json",
        provider="offline-test-provider",
        model="frozen-model",
        frozen_assets_sha256="b" * 64,
    )
    succeeded = account([attempt(
        1,
        "succeeded",
        usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
    )], limit=1)
    assert gate.record_attempt(succeeded) == "passed"
    gate.assert_ab_start_allowed()
    assert gate.state["attempts"][0]["successful_response_usage_status"] == "complete"
    assert "input_tokens" not in gate.state["attempts"][0]
    assert "output_tokens" not in gate.state["attempts"][0]


def test_protocol_choices_are_frozen_before_new_real_data():
    snapshot = protocol_v2_snapshot()
    assert snapshot["protocol_version"] == PROTOCOL_VERSION
    assert snapshot["total_token_budget_policy"] == TOTAL_TOKEN_BUDGET_POLICY
    assert snapshot["total_token_budget_is_hard_gate"] is False
    assert snapshot["per_request_max_tokens"] is PER_REQUEST_MAX_TOKENS is None
    assert snapshot["readiness"]["max_attempts"] == 2
    assert snapshot["readiness"]["outputs_count_toward_ab"] is False
