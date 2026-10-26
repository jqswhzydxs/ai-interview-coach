import json

import httpx
import pytest

from app.agents.deepseek_reasoning_effort_experiment_client import (
    DeepSeekReasoningEffortExperimentClient,
    safe_usage_details_record,
)
from app.agents.deepseek_client import DeepSeekClient
from app.agents.llm_client import LLMRequest


def request():
    return LLMRequest(
        system_prompt="frozen prompt v0.2",
        user_prompt='{"fixture":"frozen"}',
        response_schema_name="QuestionDraftBank",
        temperature=0.2,
    )


def clients(*, transport=None):
    kwargs = {}
    if transport is not None:
        kwargs["http_client"] = httpx.AsyncClient(transport=transport)
    return {
        effort: DeepSeekReasoningEffortExperimentClient(
            api_key="offline-test-key",
            model_name="deepseek-v4-pro",
            reasoning_effort=effort,
            base_url="https://provider.invalid",
            **kwargs,
        )
        for effort in ("high", "low")
    }


def test_baseline_and_candidate_payloads_differ_only_by_reasoning_effort():
    pair = clients()
    baseline = pair["high"].request_payload(request())
    candidate = pair["low"].request_payload(request())
    assert baseline["thinking"] == {"type": "enabled"}
    assert candidate["thinking"] == {"type": "enabled"}
    assert baseline["reasoning_effort"] == "high"
    assert candidate["reasoning_effort"] == "low"
    assert {key: value for key, value in baseline.items() if key != "reasoning_effort"} == {
        key: value for key, value in candidate.items() if key != "reasoning_effort"
    }


@pytest.mark.asyncio
async def test_http_transport_receives_thinking_field_and_whitelisted_usage_only():
    captured = []

    def handler(raw_request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(raw_request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"ok":true}',
                            "reasoning_content": "PRIVATE_COT_MUST_NOT_SURVIVE",
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 250,
                    "total_tokens": 350,
                    "completion_tokens_details": {
                        "reasoning_tokens": 200,
                        "visible_tokens": 50,
                        "untrusted_text": "MUST_NOT_SURVIVE",
                    },
                    "prompt_tokens_details": {"cached_tokens": 40},
                },
                "raw_provider_field": "MUST_NOT_SURVIVE",
            },
            request=raw_request,
        )

    transport = httpx.MockTransport(handler)
    pair = clients(transport=transport)
    try:
        baseline = await pair["high"].generate_json(request())
        candidate = await pair["low"].generate_json(request())
    finally:
        await pair["high"].http_client.aclose()
    assert [body["thinking"] for body in captured] == [
        {"type": "enabled"},
        {"type": "enabled"},
    ]
    assert [body["reasoning_effort"] for body in captured] == ["high", "low"]
    assert {
        key: value for key, value in captured[0].items() if key != "reasoning_effort"
    } == {
        key: value for key, value in captured[1].items() if key != "reasoning_effort"
    }
    details = safe_usage_details_record(candidate)
    assert details["reasoning_tokens"] == {"status": "available", "value": 200}
    assert details["visible_completion_tokens"] == {"status": "available", "value": 50}
    assert details["cached_input_tokens"] == {"status": "available", "value": 40}
    serialized = json.dumps(candidate.model_dump(mode="json"))
    assert "PRIVATE_COT_MUST_NOT_SURVIVE" not in serialized
    assert "MUST_NOT_SURVIVE" not in serialized
    assert "usage_details" not in serialized
    assert baseline.usage.output_tokens == candidate.usage.output_tokens == 250


@pytest.mark.asyncio
async def test_missing_usage_details_are_unknown_and_never_inferred():
    def handler(raw_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"ok":true}'}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                },
            },
            request=raw_request,
        )

    client = clients(transport=httpx.MockTransport(handler))["low"]
    try:
        response = await client.generate_json(request())
    finally:
        await client.http_client.aclose()
    assert all(
        detail == {"status": "unknown", "value": None}
        for detail in safe_usage_details_record(response).values()
    )


def test_invalid_or_implicit_reasoning_effort_is_rejected():
    with pytest.raises(ValueError, match="explicitly high or low"):
        DeepSeekReasoningEffortExperimentClient(
            api_key="offline",
            model_name="deepseek-v4-pro",
            reasoning_effort="auto",  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_production_deepseek_client_has_no_experiment_thinking_field():
    captured = []

    def handler(raw_request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(raw_request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok":true}'}}]},
            request=raw_request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        client = DeepSeekClient(
            api_key="offline",
            model_name="deepseek-v4-pro",
            base_url="https://provider.invalid",
            http_client=transport,
        )
        await client.generate_json(request())
    assert "thinking" not in captured[0]
    assert "reasoning_effort" not in captured[0]
