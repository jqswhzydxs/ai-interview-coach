from app.services.provider_usage_details import (
    historical_usage_detail_audit,
    parse_provider_usage_details,
)


def test_whitelisted_numeric_details_are_extracted_without_raw_payload():
    result = parse_provider_usage_details(
        {
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 200,
                "completion_tokens_details": {
                    "reasoning_tokens": 120,
                    "visible_tokens": 80,
                    "untrusted_text": "must not be copied",
                },
                "prompt_tokens_details": {
                    "cached_tokens": 40,
                    "untrusted_nested": {"secret": "must not be copied"},
                },
            },
            "choices": [{"message": {"content": "must not be copied"}}],
        }
    )
    assert result["capture_status"] == "available"
    assert result["fields"]["reasoning_tokens"] == {
        "status": "available",
        "value": 120,
        "source_path": "usage.completion_tokens_details.reasoning_tokens",
    }
    assert result["fields"]["visible_completion_tokens"]["value"] == 80
    assert result["fields"]["cached_input_tokens"]["value"] == 40
    assert result["visible_tokens_derived"] is False
    encoded = str(result)
    assert "must not be copied" not in encoded
    assert "secret" not in encoded


def test_missing_detail_fields_are_unsupported_and_never_zero_filled():
    result = parse_provider_usage_details(
        {"usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}}
    )
    assert result["capture_status"] == "unsupported"
    assert all(
        field == {"status": "unsupported", "value": None, "source_path": None}
        for field in result["fields"].values()
    )


def test_missing_usage_and_invalid_values_remain_unknown():
    absent = parse_provider_usage_details({})
    assert absent["capture_status"] == "unknown"
    assert absent["fields"]["reasoning_tokens"]["value"] is None

    invalid = parse_provider_usage_details(
        {
            "usage": {
                "completion_tokens_details": {"reasoning_tokens": True},
                "input_tokens_details": {"cached_tokens": -1},
            }
        }
    )
    assert invalid["fields"]["reasoning_tokens"]["status"] == "unknown"
    assert invalid["fields"]["reasoning_tokens"]["value"] is None
    assert invalid["fields"]["cached_input_tokens"]["status"] == "unknown"


def test_visible_tokens_are_not_inferred_from_completion_minus_reasoning():
    result = parse_provider_usage_details(
        {
            "usage": {
                "completion_tokens": 200,
                "completion_tokens_details": {"reasoning_tokens": 120},
            }
        }
    )
    assert result["fields"]["reasoning_tokens"]["value"] == 120
    assert result["fields"]["visible_completion_tokens"] == {
        "status": "unsupported",
        "value": None,
        "source_path": None,
    }
    assert result["visible_tokens_derived"] is False


def test_historical_audit_does_not_claim_provider_non_support():
    audit = historical_usage_detail_audit()
    assert audit["record_type"] == "phase_2_4d_c_provider_usage_details_audit"
    assert audit["reasoning_tokens"]["status"] == "unknown"
    assert audit["visible_completion_tokens"]["status"] == "unknown"
    assert audit["cached_input_token_details"]["status"] == "unknown"
    assert audit["provider_support_conclusion"] == "unknown"
    assert audit["inference_policy"]["missing_values_are_zero"] is False
