"""Safe, offline parsing for optional Provider usage-detail counters.

The parser accepts an already-decoded SDK/response mapping and returns only
whitelisted non-negative integer counters.  It deliberately does not retain the
source object and never derives visible tokens by subtraction.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


DETAIL_FIELDS: dict[str, tuple[tuple[str, ...], ...]] = {
    "reasoning_tokens": (
        ("completion_tokens_details", "reasoning_tokens"),
        ("output_tokens_details", "reasoning_tokens"),
        ("reasoning_tokens",),
    ),
    "visible_completion_tokens": (
        ("completion_tokens_details", "visible_tokens"),
        ("output_tokens_details", "visible_tokens"),
        ("visible_completion_tokens",),
    ),
    "cached_input_tokens": (
        ("prompt_tokens_details", "cached_tokens"),
        ("input_tokens_details", "cached_tokens"),
        ("cached_tokens",),
    ),
    "cache_read_input_tokens": (
        ("prompt_tokens_details", "cache_read_tokens"),
        ("input_tokens_details", "cache_read_tokens"),
        ("cache_read_input_tokens",),
    ),
    "cache_creation_input_tokens": (
        ("prompt_tokens_details", "cache_creation_tokens"),
        ("input_tokens_details", "cache_creation_tokens"),
        ("cache_creation_input_tokens",),
    ),
}


def _non_negative_int(value: object) -> int | None:
    if type(value) is int and value >= 0:
        return value
    return None


def _at_path(source: Mapping[str, Any], path: Sequence[str]) -> tuple[bool, object]:
    current: object = source
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return False, None
        current = current[key]
    return True, current


def parse_provider_usage_details(response: Mapping[str, Any]) -> dict[str, Any]:
    """Extract only explicit usage detail counters from a response mapping.

    ``unknown`` means there was no usable usage mapping. ``unsupported`` means
    a usage mapping was observed but it exposed none of the whitelisted paths.
    Invalid values remain unknown and are never coerced to zero.
    """

    raw_usage = response.get("usage") if isinstance(response, Mapping) else None
    if not isinstance(raw_usage, Mapping):
        return {
            "capture_status": "unknown",
            "fields": {
                name: {"status": "unknown", "value": None, "source_path": None}
                for name in DETAIL_FIELDS
            },
            "visible_tokens_derived": False,
            "raw_response_retained": False,
        }

    fields: dict[str, dict[str, Any]] = {}
    for name, paths in DETAIL_FIELDS.items():
        found_invalid = False
        for path in paths:
            found, raw_value = _at_path(raw_usage, path)
            if not found:
                continue
            value = _non_negative_int(raw_value)
            if value is not None:
                fields[name] = {
                    "status": "available",
                    "value": value,
                    "source_path": "usage." + ".".join(path),
                }
                break
            found_invalid = True
        else:
            fields[name] = {
                "status": "unknown" if found_invalid else "unsupported",
                "value": None,
                "source_path": None,
            }

    return {
        "capture_status": (
            "available"
            if any(field["status"] == "available" for field in fields.values())
            else "unsupported"
        ),
        "fields": fields,
        "visible_tokens_derived": False,
        "raw_response_retained": False,
    }


def historical_usage_detail_audit() -> dict[str, Any]:
    """Describe the bounded conclusion supported by the current capture model."""

    return {
        "record_type": "phase_2_4d_c_provider_usage_details_audit",
        "audit_scope": "stored_ab1_usage_and_current_capture_source",
        "historical_response_available": False,
        "current_stored_usage_fields": [
            "input_tokens",
            "output_tokens",
            "total_tokens",
        ],
        "reasoning_tokens": {
            "status": "unknown",
            "reason": "historical_capture_did_not_retain_whitelisted_detail_fields",
        },
        "visible_completion_tokens": {
            "status": "unknown",
            "reason": "no_explicit_visible_token_counter_was_retained",
        },
        "cached_input_token_details": {
            "status": "unknown",
            "reason": "historical_capture_did_not_retain_whitelisted_detail_fields",
        },
        "provider_support_conclusion": "unknown",
        "provider_support_reason": (
            "The stored evidence cannot distinguish Provider non-support from detail "
            "fields discarded by the existing three-field TokenUsage capture model."
        ),
        "inference_policy": {
            "derive_visible_from_output_minus_reasoning": False,
            "missing_values_are_zero": False,
            "allowed_values": "explicit non-negative integers at whitelisted SDK/response paths",
        },
        "sensitive_data_persisted": False,
    }
