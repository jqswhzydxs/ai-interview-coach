import hashlib
import json
from types import SimpleNamespace

import httpx
import pytest

from app.agents.deepseek_prompt_recovery_experiment_client import (
    DeepSeekPromptRecoveryExperimentResponse,
    WhitelistedUsageDetails,
)
from app.agents.llm_client import LLMResponse, TokenUsage
from app.core.config import Settings
from app.services.question_draft_provider_readiness_v5 import (
    QuestionDraftProviderReadinessV5Config,
    QuestionDraftProviderReadinessV5Error,
    QuestionDraftProviderReadinessV5Runner,
)
from scripts.run_question_draft_provider_readiness_v5 import (
    require_real_readiness_authorization,
)
from tests.unit.test_question_bank_draft_protocol import _valid_draft


class ReadinessClient:
    provider = "deepseek"
    model_name = "deepseek-v4-pro"
    thinking_type = "disabled"
    reasoning_effort = None

    def __init__(self, actions):
        self.actions = list(actions)
        self.calls = 0
        self.requests = []

    def request_payload(self, request):
        return {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": request.temperature,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
        }

    async def generate_json(self, request):
        self.calls += 1
        self.requests.append(request)
        action = self.actions[self.calls - 1]
        if isinstance(action, BaseException):
            raise action
        content, usage, details = action
        cls = DeepSeekPromptRecoveryExperimentResponse if details else LLMResponse
        kwargs = {"usage_details": details} if details else {}
        return cls(
            provider=self.provider,
            model_name=self.model_name,
            content=content,
            usage=usage,
            raw_text="RAW_READINESS_RESPONSE_MUST_NOT_BE_PERSISTED",
            **kwargs,
        )


USAGE = TokenUsage(input_tokens=100, output_tokens=200, total_tokens=300)


def success(*, usage=USAGE, content=None, details=None):
    return (content or _valid_draft("Go"), usage, details)


def runner(tmp_path, client):
    return QuestionDraftProviderReadinessV5Runner(
        llm_client=client,
        config=QuestionDraftProviderReadinessV5Config(
            ledger_path=tmp_path / "readiness-v5.json"
        ),
    )


@pytest.mark.asyncio
async def test_readiness_success_is_one_candidate_prompt_call_without_retry_or_fallback(tmp_path):
    details = WhitelistedUsageDetails(reasoning_tokens=150, visible_completion_tokens=50)
    client = ReadinessClient([success(details=details)])
    readiness = runner(tmp_path, client)
    assert readiness.prepare().ledger["status"] == "pending"
    result = await readiness.attempt()
    assert result.ledger["status"] == "passed"
    assert client.calls == 1
    record = result.ledger["attempts"][0]
    assert record["provider_call_count"] == 1
    assert record["retry_count"] == 0
    assert record["fallback_used"] is False
    assert record["thinking"] == {"type": "disabled"}
    assert record["reasoning_effort"] is None
    assert record["reasoning_effort_present"] is False
    assert result.ledger["assets"]["prompt"]["version"] == "question_bank_draft_agent_v0.3"
    assert record["provider_call"]["usage_details"]["reasoning_tokens"] == {
        "status": "available",
        "value": 150,
    }
    serialized = result.ledger_path.read_text(encoding="utf-8")
    assert "RAW_READINESS_RESPONSE_MUST_NOT_BE_PERSISTED" not in serialized
    assert '"input"' not in serialized and '"output"' not in serialized


@pytest.mark.asyncio
async def test_readiness_failure_then_success_reuses_ledger_and_terminal_is_idempotent(tmp_path):
    failure = httpx.RemoteProtocolError(
        "uncontrolled response body",
        request=httpx.Request("POST", "https://provider.invalid"),
    )
    client = ReadinessClient([failure, success()])
    readiness = runner(tmp_path, client)
    readiness.prepare()
    first = await readiness.attempt()
    assert first.ledger["status"] == "pending"
    assert first.ledger["attempts"][0]["provider_call"]["usage_details"]["reasoning_tokens"] == {
        "status": "unknown",
        "value": None,
    }
    second = await readiness.attempt()
    assert second.ledger["status"] == "passed"
    before = hashlib.sha256(second.ledger_path.read_bytes()).hexdigest()
    duplicate = await readiness.attempt()
    assert duplicate.ledger["status"] == "passed"
    assert client.calls == 2
    assert hashlib.sha256(second.ledger_path.read_bytes()).hexdigest() == before
    assert "uncontrolled response body" not in second.ledger_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_two_failures_block_permanently_and_missing_usage_or_content_cannot_pass(tmp_path):
    failures = [
        httpx.RemoteProtocolError("one", request=httpx.Request("POST", "https://provider.invalid")),
        httpx.RemoteProtocolError("two", request=httpx.Request("POST", "https://provider.invalid")),
    ]
    blocked_client = ReadinessClient(failures)
    blocked = runner(tmp_path / "blocked", blocked_client)
    blocked.prepare()
    await blocked.attempt()
    assert (await blocked.attempt()).ledger["status"] == "blocked"
    assert (await blocked.attempt()).ledger["status"] == "blocked"
    assert blocked_client.calls == 2

    missing = runner(tmp_path / "missing", ReadinessClient([success(usage=None)]))
    missing.prepare()
    missing_record = (await missing.attempt()).ledger["attempts"][0]
    assert missing_record["passed"] is False
    assert missing_record["successful_response_usage"]["status"] == "unknown"

    invalid = runner(
        tmp_path / "invalid",
        ReadinessClient([success(content={"invalid": True})]),
    )
    invalid.prepare()
    invalid_record = (await invalid.attempt()).ledger["attempts"][0]
    assert invalid_record["passed"] is False
    assert invalid_record["content_checks"]["draft_schema"] == "failed"


def test_readiness_rejects_identity_or_request_control_drift_before_ledger(tmp_path):
    for attribute, value in (
        ("provider", "kimi"),
        ("model_name", "deepseek-chat"),
        ("thinking_type", "enabled"),
        ("reasoning_effort", "high"),
    ):
        client = ReadinessClient([success()])
        setattr(client, attribute, value)
        ledger = tmp_path / attribute / "readiness-v5.json"
        with pytest.raises(QuestionDraftProviderReadinessV5Error):
            QuestionDraftProviderReadinessV5Runner(
                llm_client=client,
                config=QuestionDraftProviderReadinessV5Config(ledger_path=ledger),
            )
        assert not ledger.exists()


@pytest.mark.parametrize(
    "authorized,real_enabled,full_logs,model,expected",
    [
        (False, True, False, "deepseek-v4-pro", "authorize-phase-2-4d-f-a-readiness"),
        (True, False, False, "deepseek-v4-pro", "RUN_REAL_LLM_ACCEPTANCE"),
        (True, True, True, "deepseek-v4-pro", "SAVE_FULL_LLM_LOGS"),
        (True, True, False, "deepseek-chat", "deepseek-v4-pro"),
    ],
)
def test_readiness_cli_authorization_stops_before_provider_call(
    authorized, real_enabled, full_logs, model, expected
):
    args = SimpleNamespace(authorize_phase_2_4d_f_a_readiness=authorized)
    settings = Settings(
        APP_ENV="test",
        LLM_PROVIDER="deepseek",
        LLM_MODEL=model,
        DEEPSEEK_API_KEY="offline-only",
        RUN_REAL_LLM_ACCEPTANCE=real_enabled,
        SAVE_FULL_LLM_LOGS=full_logs,
    )
    with pytest.raises(SystemExit, match=expected):
        require_real_readiness_authorization(args, settings)

