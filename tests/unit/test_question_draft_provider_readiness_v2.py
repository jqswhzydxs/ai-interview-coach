import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.agents.llm_client import LLMResponse, TokenUsage
from app.core.config import Settings
from app.services.question_draft_provider_readiness_v2 import (
    QuestionDraftProviderReadinessV2Config,
    QuestionDraftProviderReadinessV2Runner,
    load_and_validate_readiness_ledger,
)
from scripts.run_question_draft_provider_readiness_v2 import (
    require_real_readiness_authorization,
)
from scripts.run_question_draft_token_experiment_v2 import require_real_ab_authorization
from tests.unit.test_question_bank_draft_protocol import _valid_draft


class ReadinessProvider:
    provider = "offline-readiness"
    model_name = "frozen-readiness-model"

    def __init__(self, actions):
        self.actions = list(actions)
        self.calls = 0
        self.requests = []

    async def generate_json(self, request):
        self.calls += 1
        self.requests.append(request)
        action = self.actions[self.calls - 1]
        if isinstance(action, BaseException):
            raise action
        content, usage = action
        return LLMResponse(
            provider=self.provider,
            model_name=self.model_name,
            content=content,
            usage=usage,
            raw_text="RAW_READINESS_RESPONSE_MUST_NOT_BE_PERSISTED",
        )


COMPLETE_USAGE = TokenUsage(input_tokens=100, output_tokens=200, total_tokens=300)


def success(*, usage=COMPLETE_USAGE, content=None):
    return (content or _valid_draft("Go"), usage)


def runner(tmp_path, provider):
    return QuestionDraftProviderReadinessV2Runner(
        llm_client=provider,
        config=QuestionDraftProviderReadinessV2Config(
            ledger_path=tmp_path / "readiness-v2.json"
        ),
    )


@pytest.mark.asyncio
async def test_readiness_first_attempt_success_is_single_call_real_and_safe(tmp_path):
    provider = ReadinessProvider([success()])
    readiness = runner(tmp_path, provider)
    prepared = readiness.prepare()
    assert prepared.ledger["status"] == "pending"
    assert provider.calls == 0

    artifacts = await readiness.attempt()
    assert provider.calls == 1
    assert artifacts.ledger["status"] == "passed"
    record = artifacts.ledger["attempts"][0]
    assert record["provider_call_count"] == 1
    assert record["retry_count"] == 0
    assert record["fallback_used"] is False
    assert record["successful_response_usage"]["status"] == "complete"
    assert record["billing_usage_completeness"]["status"] == "complete"
    assert set(record["content_checks"].values()) == {"passed"}
    assert provider.requests[0].response_schema_name == "QuestionDraftBank"
    assert provider.requests[0].temperature == 0.2
    serialized = artifacts.ledger_path.read_text(encoding="utf-8")
    assert "RAW_READINESS_RESPONSE_MUST_NOT_BE_PERSISTED" not in serialized
    assert '"input"' not in serialized and '"output"' not in serialized


@pytest.mark.asyncio
async def test_first_network_failure_second_success_uses_same_ledger(tmp_path):
    failure = httpx.RemoteProtocolError(
        "uncontrolled failure body",
        request=httpx.Request("POST", "https://provider.invalid"),
    )
    provider = ReadinessProvider([failure, success()])
    readiness = runner(tmp_path, provider)
    readiness.prepare()
    first = await readiness.attempt()
    assert first.ledger["status"] == "pending"
    assert first.ledger["attempts"][0]["provider_call"]["failure_category"] == "network"
    assert first.ledger["attempts"][0]["provider_call"]["exception_type"] == "RemoteProtocolError"
    ledger_path = first.ledger_path

    second = await readiness.attempt()
    assert second.ledger_path == ledger_path
    assert second.ledger["status"] == "passed"
    assert len(second.ledger["attempts"]) == 2
    assert provider.calls == 2
    assert "uncontrolled failure body" not in ledger_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_two_failures_are_permanently_blocked_and_terminal_attempt_is_idempotent(tmp_path):
    failures = [
        httpx.RemoteProtocolError(
            "first", request=httpx.Request("POST", "https://provider.invalid")
        ),
        httpx.RemoteProtocolError(
            "second", request=httpx.Request("POST", "https://provider.invalid")
        ),
    ]
    provider = ReadinessProvider(failures)
    readiness = runner(tmp_path, provider)
    readiness.prepare()
    await readiness.attempt()
    blocked = await readiness.attempt()
    assert blocked.ledger["status"] == "blocked"
    before = hashlib.sha256(blocked.ledger_path.read_bytes()).hexdigest()
    duplicate = await readiness.attempt()
    after = hashlib.sha256(blocked.ledger_path.read_bytes()).hexdigest()
    assert duplicate.ledger["status"] == "blocked"
    assert provider.calls == 2
    assert after == before


@pytest.mark.asyncio
async def test_missing_usage_and_content_failure_cannot_pass(tmp_path):
    missing_provider = ReadinessProvider([success(usage=None)])
    missing = runner(tmp_path / "missing", missing_provider)
    missing.prepare()
    missing_result = await missing.attempt()
    assert missing_result.ledger["status"] == "pending"
    missing_record = missing_result.ledger["attempts"][0]
    assert missing_record["successful_response_usage"]["status"] == "unknown"
    assert missing_record["billing_usage_completeness"]["status"] == "incomplete"
    assert missing_record["known_token_lower_bound"]["total_tokens"] is None

    invalid_provider = ReadinessProvider([success(content={"invalid": True})])
    invalid = runner(tmp_path / "invalid", invalid_provider)
    invalid.prepare()
    invalid_result = await invalid.attempt()
    assert invalid_result.ledger["status"] == "pending"
    invalid_record = invalid_result.ledger["attempts"][0]
    assert invalid_record["content_checks"]["draft_schema"] == "failed"
    assert invalid_record["passed"] is False
    assert invalid_record["fallback_used"] is False
    assert invalid_provider.calls == 1


@pytest.mark.asyncio
async def test_duplicate_successful_attempt_is_idempotent(tmp_path):
    provider = ReadinessProvider([success()])
    readiness = runner(tmp_path, provider)
    readiness.prepare()
    first = await readiness.attempt()
    before = first.ledger_path.read_bytes()
    second = await readiness.attempt()
    assert second.ledger["status"] == "passed"
    assert provider.calls == 1
    assert first.ledger_path.read_bytes() == before


def test_ledger_identity_and_asset_drift_are_rejected(tmp_path):
    provider = ReadinessProvider([success()])
    readiness = runner(tmp_path, provider)
    artifacts = readiness.prepare()
    with pytest.raises(Exception, match="provider drift"):
        load_and_validate_readiness_ledger(
            artifacts.ledger_path,
            provider="different-provider",
            model=provider.model_name,
            require_passed=False,
        )
    ledger = json.loads(artifacts.ledger_path.read_text(encoding="utf-8"))
    ledger["assets"]["prompt"]["sha256"] = "0" * 64
    artifacts.ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    with pytest.raises(Exception, match="assets drift"):
        load_and_validate_readiness_ledger(
            artifacts.ledger_path,
            provider=provider.provider,
            model=provider.model_name,
            require_passed=False,
        )


@pytest.mark.parametrize(
    "authorized,real_enabled,full_logs,expected",
    [
        (False, True, False, "authorize-phase-2-4d-b-readiness"),
        (True, False, False, "RUN_REAL_LLM_ACCEPTANCE"),
        (True, True, True, "SAVE_FULL_LLM_LOGS"),
    ],
)
def test_readiness_cli_double_authorization_fails_before_client_use(
    authorized, real_enabled, full_logs, expected
):
    args = SimpleNamespace(authorize_phase_2_4d_b_readiness=authorized)
    settings = Settings(
        APP_ENV="test",
        LLM_PROVIDER="deepseek",
        LLM_MODEL="frozen-model",
        DEEPSEEK_API_KEY="configured-for-offline-authorization-test",
        RUN_REAL_LLM_ACCEPTANCE=real_enabled,
        SAVE_FULL_LLM_LOGS=full_logs,
    )
    with pytest.raises(SystemExit, match=expected):
        require_real_readiness_authorization(args, settings)


def test_ab_cli_is_disabled_without_explicit_authorization():
    args = SimpleNamespace(authorize_phase_2_4d_b2_ab=False)
    settings = Settings(
        APP_ENV="test",
        LLM_PROVIDER="deepseek",
        LLM_MODEL="frozen-model",
        DEEPSEEK_API_KEY="configured-for-offline-authorization-test",
        RUN_REAL_LLM_ACCEPTANCE=True,
        SAVE_FULL_LLM_LOGS=False,
    )
    with pytest.raises(SystemExit, match="authorize-phase-2-4d-b2-ab"):
        require_real_ab_authorization(args, settings)
