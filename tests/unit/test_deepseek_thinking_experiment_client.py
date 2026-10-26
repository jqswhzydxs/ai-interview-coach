import json

import httpx
import pytest

from app.agents.deepseek_thinking_experiment_client import (
    DeepSeekThinkingExperimentClient,
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
        mode: DeepSeekThinkingExperimentClient(
            api_key="offline-test-key",
            model_name="deepseek-v4-pro",
            thinking_type=mode,
            base_url="https://provider.invalid",
            **kwargs,
        )
        for mode in ("enabled", "disabled")
    }


def test_baseline_and_candidate_payloads_differ_only_by_thinking_type():
    pair = clients()
    baseline = pair["enabled"].request_payload(request())
    candidate = pair["disabled"].request_payload(request())
    assert baseline["thinking"] == {"type": "enabled"}
    assert candidate["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in baseline
    assert "reasoning_effort" not in candidate
    assert {key: value for key, value in baseline.items() if key != "thinking"} == {
        key: value for key, value in candidate.items() if key != "thinking"
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
        baseline = await pair["enabled"].generate_json(request())
        candidate = await pair["disabled"].generate_json(request())
    finally:
        await pair["enabled"].http_client.aclose()
    assert [body["thinking"] for body in captured] == [
        {"type": "enabled"},
        {"type": "disabled"},
    ]
    assert all("reasoning_effort" not in body for body in captured)
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

    client = clients(transport=httpx.MockTransport(handler))["disabled"]
    try:
        response = await client.generate_json(request())
    finally:
        await client.http_client.aclose()
    assert all(
        detail == {"status": "unknown", "value": None}
        for detail in safe_usage_details_record(response).values()
    )


def test_invalid_or_implicit_thinking_mode_is_rejected():
    with pytest.raises(ValueError, match="explicitly enabled or disabled"):
        DeepSeekThinkingExperimentClient(
            api_key="offline",
            model_name="deepseek-v4-pro",
            thinking_type="auto",  # type: ignore[arg-type]
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
