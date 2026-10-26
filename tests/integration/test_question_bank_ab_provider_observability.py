import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

import httpx
import pytest

from app.agents.deepseek_client import DeepSeekClient
from app.agents.llm_client import LLMResponseError, TokenUsage
from app.services.provider_failure_observability import provider_failure_fields
from app.services.question_bank_ab_service import (
    QuestionBankABAuditError,
    QuestionBankABConfig,
    QuestionBankABRunner,
)
from tests.integration.test_question_bank_ab_runner import PairedFakeProvider, _config


SENSITIVE = "OFFLINE_SENSITIVE_SENTINEL_MUST_NEVER_BE_SAVED"
FAKE_CREDENTIAL = "sk-OFFLINE-TEST-CREDENTIAL-DO-NOT-SAVE"
REQUEST_ID = "req_0123456789abcdef"
ATTEMPT_FIELDS = {
    "variant", "case_id", "pair", "attempt", "call_index", "status",
    "started_at", "finished_at", "failure_category", "exception_type",
    "http_status_code", "provider_error_code", "request_id", "retry_after",
    "filtered_fields", "latency_ms", "token_usage_available",
    "token_usage_status", "token_usage",
}


def _http_error(status=429, code="rate_limit_exceeded", *, headers=None):
    request = httpx.Request(
        "POST", f"https://offline.invalid/{SENSITIVE}",
        headers={"Authorization": f"Bearer {FAKE_CREDENTIAL}"},
        content=SENSITIVE,
    )
    response = httpx.Response(
        status, request=request,
        json={"error": {"code": code, "message": SENSITIVE}, "raw": FAKE_CREDENTIAL},
        headers=headers or {"x-request-id": REQUEST_ID, "retry-after": "15"},
    )
    return httpx.HTTPStatusError(SENSITIVE, request=request, response=response)


def _assert_no_sensitive_files(run_dir, *extra):
    for path in run_dir.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            for value in (SENSITIVE, FAKE_CREDENTIAL, "RAW_PROVIDER_RESPONSE_MUST_NOT_BE_SAVED", *extra):
                assert value not in text, path.name
            assert "Authorization" not in text
            assert "Bearer " not in text


@pytest.mark.asyncio
@pytest.mark.parametrize("status,code,category", [
    (401, "invalid_api_key", "auth"),
    (403, "model_access_denied", "permission"),
    (429, "rate_limit_exceeded", "rate_limit"),
    (400, "invalid_request_error", "invalid_request"),
    (500, "server_error", "provider_server"),
    (502, "server_error", "provider_server"),
    (503, "service_unavailable", "provider_server"),
])
async def test_http_failures_are_whitelisted_and_persisted(tmp_path, status, code, category):
    seen = []

    def transport(request):
        seen.append(request)
        return httpx.Response(
            status,
            json={"error": {"code": code, "message": SENSITIVE}, "raw": FAKE_CREDENTIAL},
            headers={"x-request-id": REQUEST_ID, "retry-after": "15"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
        provider = DeepSeekClient(api_key=FAKE_CREDENTIAL, model_name="offline-model", http_client=http)
        runner = QuestionBankABRunner(llm_client=provider, config=_config(tmp_path))
        artifacts = await runner.run_smoke()

    assert len(seen) == 1
    manifest = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
    audit = artifacts.report["provider_attempts"]
    assert audit == manifest["provider_attempts"]
    assert len(audit) == 1
    failure = audit[0]
    assert set(failure) == ATTEMPT_FIELDS
    assert (failure["variant"], failure["case_id"], failure["pair"], failure["attempt"]) == (
        "smoke", "provider_smoke", 0, 1,
    )
    assert failure["status"] == "failed"
    assert failure["failure_category"] == category
    assert failure["exception_type"] == "HTTPStatusError"
    assert failure["http_status_code"] == status
    assert failure["provider_error_code"] == code
    assert failure["request_id"] == REQUEST_ID
    assert failure["retry_after"] == "15"
    assert failure["latency_ms"] >= 0
    assert failure["token_usage_available"] is False
    assert failure["token_usage_status"] == "not_available"
    assert all(value is None for value in failure["token_usage"].values())
    assert artifacts.report["smoke"]["token_usage"]["total_tokens"] is None
    assert artifacts.report["budget"]["total_tokens_used"] is None
    assert artifacts.report["budget"]["known_token_usage"]["total_tokens"] == 0
    assert artifacts.report["budget"]["missing_usage_failure_calls"] == 1
    markdown = artifacts.report_markdown_path.read_text(encoding="utf-8")
    assert category in markdown
    assert "unknown/not_available" in markdown
    _assert_no_sensitive_files(runner.config.run_dir)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,category", [
    (httpx.ConnectTimeout, "connect_timeout"),
    (httpx.ReadTimeout, "read_timeout"),
    (httpx.ConnectError, "network"),
    (httpx.ReadError, "network"),
    (httpx.RemoteProtocolError, "network"),
])
async def test_transport_failures_have_no_exception_text(tmp_path, kind, category):
    def transport(request):
        raise kind(SENSITIVE, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
        provider = DeepSeekClient(api_key=FAKE_CREDENTIAL, model_name="offline-model", http_client=http)
        runner = QuestionBankABRunner(llm_client=provider, config=_config(tmp_path))
        artifacts = await runner.run_smoke()
    failure = artifacts.report["provider_attempts"][0]
    assert failure["failure_category"] == category
    assert failure["exception_type"] == kind.__name__
    assert failure["http_status_code"] is None
    assert failure["provider_error_code"] is None
    _assert_no_sensitive_files(runner.config.run_dir)


class CandidateFailureProvider(PairedFakeProvider):
    api_key = FAKE_CREDENTIAL

    def __init__(self, run_dir, *, recover=False, error=None):
        super().__init__()
        self.run_dir = run_dir
        self.recover = recover
        self.error = error
        self.go_attempts = 0
        self.checkpoint_verified = False

    async def generate_json(self, request):
        is_go_candidate = (
            request.response_schema_name == "QuestionDraftBank"
            and json.loads(request.user_prompt)["resume_profile"]["skills"][0] == "Go"
        )
        if not is_go_candidate:
            return await super().generate_json(request)
        self.go_attempts += 1
        if self.go_attempts == 2:
            for name in ("manifest.json", "question-bank-ab-report.json"):
                disk = json.loads((self.run_dir / name).read_text(encoding="utf-8"))
                go = [item for item in disk["provider_attempts"] if item["variant"] == "candidate"]
                assert go[0]["status"] == "failed"
                assert go[0]["attempt"] == 1
                assert go[1]["status"] == "started"
                assert go[1]["attempt"] == 2
                # Candidate execution has not yet returned or been appended to runs.
                assert not any(run["variant"] == "candidate" for run in disk["runs"])
            markdown = (self.run_dir / "question-bank-ab-report.md").read_text(encoding="utf-8")
            assert "HTTPStatusError" in markdown or "LLMResponseError" in markdown
            self.checkpoint_verified = True
            if self.recover:
                return await super().generate_json(request)
        self.requests.append(request)
        raise self.error or _http_error()


@pytest.mark.asyncio
async def test_two_candidate_failures_are_saved_before_retry_and_preserve_fallback(tmp_path, monkeypatch):
    from sqlalchemy.engine import Engine

    def database_forbidden(*args, **kwargs):
        raise AssertionError("report-only A/B must not connect to a database")

    monkeypatch.setattr(Engine, "connect", database_forbidden)
    config = _config(tmp_path)
    provider = CandidateFailureProvider(config.run_dir)
    runner = QuestionBankABRunner(llm_client=provider, config=config)
    await runner.run_smoke()
    artifacts = await runner.run_pilot()
    failures = [item for item in artifacts.report["provider_attempts"] if item["status"] == "failed"]
    assert provider.checkpoint_verified
    assert len(failures) == 2
    assert [item["attempt"] for item in failures] == [1, 2]
    assert all((item["variant"], item["case_id"], item["pair"]) == (
        "candidate", "backend_go_case", 1,
    ) for item in failures)
    assert all(item["failure_category"] == "rate_limit" for item in failures)
    run = next(run for run in artifacts.report["runs"] if run["variant"] == "candidate")
    assert run["execution_mode"] == "fallback"
    assert run["provider_calls"] == 2
    assert run["retry_count"] == 1
    assert run["assembler_passed"] == "not_evaluated"
    assert all(value is None for value in run["token_usage"].values())
    candidate = artifacts.report["summary"]["variants"]["candidate"]
    assert all(value is None for value in candidate["token_usage"].values())
    assert candidate["known_token_usage"]["total_tokens"] == 120
    assert artifacts.report["budget"]["total_tokens_used"] is None
    assert artifacts.report["pilot"]["candidate_real_count"] == 2
    assert artifacts.report["provider_observability"]["mode"] == "report_only"
    _assert_no_sensitive_files(config.run_dir, *(
        value for request in provider.requests
        for value in (request.system_prompt, request.user_prompt)
    ))


@pytest.mark.asyncio
@pytest.mark.parametrize("known_failure_usage", [False, True])
async def test_retry_success_keeps_unknown_usage_and_known_lower_bounds_separate(tmp_path, known_failure_usage):
    config = _config(tmp_path)
    error = LLMResponseError(
        SENSITIVE,
        usage=TokenUsage(input_tokens=2, output_tokens=3, total_tokens=5) if known_failure_usage else None,
    )
    provider = CandidateFailureProvider(config.run_dir, recover=True, error=error)
    runner = QuestionBankABRunner(llm_client=provider, config=config)
    await runner.run_smoke()
    artifacts = await runner.run_pilot()
    run = next(run for run in artifacts.report["runs"] if run["variant"] == "candidate")
    assert run["execution_mode"] == "real"
    assert run["provider_calls"] == 2
    assert run["token_usage"]["total_tokens"] == (65 if known_failure_usage else None)
    assert run["known_token_usage"]["total_tokens"] == (65 if known_failure_usage else 60)
    assert run["output_token_usage_available"] is known_failure_usage
    assert artifacts.report["summary"]["token_comparison"]["relative"]["comparable_pair_count"] == (
        3 if known_failure_usage else 2
    )
    _assert_no_sensitive_files(config.run_dir)


def test_unknown_exception_class_and_message_are_never_serialized():
    class UnsafeError(RuntimeError):
        def __str__(self):
            raise AssertionError("must not stringify exceptions")

        def __repr__(self):
            raise AssertionError("must not repr exceptions")

    UnsafeError.__name__ = SENSITIVE
    fields = provider_failure_fields(UnsafeError(SENSITIVE))
    assert fields["failure_category"] == "unknown_provider"
    assert fields["exception_type"] == "OtherProviderError"
    assert SENSITIVE not in json.dumps(fields)


@pytest.mark.parametrize("field,value", [
    ("provider_error_code", FAKE_CREDENTIAL),
    ("provider_error_code", SENSITIVE),
    ("request_id", FAKE_CREDENTIAL),
    ("request_id", "req_" + SENSITIVE),
    ("request_id", "req_01234567\n" + SENSITIVE),
    ("retry_after", SENSITIVE),
    ("retry_after", "15 " + FAKE_CREDENTIAL),
])
def test_untrusted_diagnostic_values_are_filtered(field, value):
    headers = {"x-request-id": REQUEST_ID, "retry-after": "15"}
    if field == "request_id":
        headers["x-request-id"] = value
    if field == "retry_after":
        headers["retry-after"] = value
    exc = _http_error(code=value if field == "provider_error_code" else "rate_limit_exceeded", headers=headers)
    fields = provider_failure_fields(exc, sensitive_values=(FAKE_CREDENTIAL, SENSITIVE))
    assert fields[field] is None
    assert field in fields["filtered_fields"]
    assert SENSITIVE not in json.dumps(fields)
    assert FAKE_CREDENTIAL not in json.dumps(fields)


def test_authorization_reflected_into_allowed_request_id_is_filtered():
    exc = _http_error(headers={"x-request-id": REQUEST_ID, "retry-after": "15"})
    exc.request.headers["Authorization"] = f"Bearer {REQUEST_ID}"
    assert provider_failure_fields(exc)["request_id"] is None


def test_lowercase_authorization_token_embedded_in_request_id_is_filtered():
    exc = _http_error(headers={"x-request-id": "req_" + REQUEST_ID})
    exc.request.headers["Authorization"] = f"bearer {REQUEST_ID}"
    assert provider_failure_fields(exc)["request_id"] is None


def test_non_http_status_is_not_accepted_as_a_diagnostic_number():
    assert provider_failure_fields(_http_error(status=700))["http_status_code"] is None


def test_retry_after_accepts_canonical_http_date():
    value = "Mon, 19 Oct 2026 14:00:00 GMT"
    fields = provider_failure_fields(_http_error(headers={"retry-after": value}))
    assert fields["retry_after"] == value


@pytest.mark.asyncio
async def test_partial_usage_never_turns_missing_fields_into_zero(tmp_path):
    class PartialProvider(PairedFakeProvider):
        async def generate_json(self, request):
            response = await super().generate_json(request)
            return response.model_copy(update={"usage": TokenUsage(total_tokens=7)})

    runner = QuestionBankABRunner(llm_client=PartialProvider(), config=_config(tmp_path))
    artifacts = await runner.run_smoke()
    audit = artifacts.report["provider_attempts"][0]
    assert audit["token_usage"] == {"input_tokens": None, "output_tokens": None, "total_tokens": 7}
    assert audit["token_usage_status"] == "unknown"
    assert audit["token_usage_available"] is False
    assert artifacts.report["budget"]["input_tokens_used"] is None
    assert artifacts.report["budget"]["total_tokens_used"] == 7


@pytest.mark.asyncio
async def test_explicit_zero_usage_is_distinct_from_missing_usage(tmp_path):
    class ZeroProvider(PairedFakeProvider):
        async def generate_json(self, request):
            response = await super().generate_json(request)
            return response.model_copy(update={
                "usage": TokenUsage(input_tokens=0, output_tokens=0, total_tokens=0),
            })

    runner = QuestionBankABRunner(llm_client=ZeroProvider(), config=_config(tmp_path))
    artifacts = await runner.run_smoke()
    audit = artifacts.report["provider_attempts"][0]
    assert audit["token_usage_available"] is True
    assert audit["token_usage_status"] == "available"
    assert audit["token_usage"]["total_tokens"] == 0
    assert artifacts.report["budget"]["total_tokens_used"] == 0


@pytest.mark.asyncio
async def test_old_report_only_manifest_does_not_invent_historical_attempts(tmp_path):
    provider = PairedFakeProvider()
    config = _config(tmp_path)
    runner = QuestionBankABRunner(llm_client=provider, config=config)
    await runner.run_smoke()
    legacy = json.loads(runner.manifest_path.read_text(encoding="utf-8"))
    del legacy["provider_observability"]
    del legacy["provider_attempts"]
    for key in ("known_token_usage", "missing_token_usage_calls", "token_usage_status"):
        del legacy["budget"][key]
    runner.manifest_path.write_text(json.dumps(legacy), encoding="utf-8")
    restored = QuestionBankABRunner(llm_client=provider, config=config)
    restored._load_or_initialize()
    assert restored._manifest["provider_observability"]["legacy_unobserved_calls"] == 1
    assert restored._manifest["provider_attempts"] == []
    assert len(provider.requests) == 1


@pytest.mark.asyncio
async def test_audit_write_failure_aborts_without_provider_retry(tmp_path, monkeypatch):
    provider = PairedFakeProvider()
    runner = QuestionBankABRunner(llm_client=provider, config=_config(tmp_path))
    await runner.run_smoke()

    def fail_write():
        raise OSError(SENSITIVE)

    monkeypatch.setattr(runner, "_persist_all", fail_write)
    cases_before = len(provider.requests)
    runner._set_provider_context("candidate", "backend_go_case", 1)
    with pytest.raises(QuestionBankABAuditError, match="audit persistence failed"):
        await runner._budgeted_client.generate_json(provider.requests[0])
    assert len(provider.requests) == cases_before


@pytest.mark.asyncio
async def test_failure_audit_write_error_does_not_reach_agent_retry(tmp_path, monkeypatch):
    from app.services import question_bank_ab_service as service

    config = _config(tmp_path)
    provider = CandidateFailureProvider(config.run_dir)
    runner = QuestionBankABRunner(llm_client=provider, config=config)
    await runner.run_smoke()
    write = service._atomic_write_text

    def fail_report_after_failure(path, text):
        if path == runner.report_json_path and '"status": "failed"' in text:
            raise OSError(SENSITIVE)
        return write(path, text)

    monkeypatch.setattr(service, "_atomic_write_text", fail_report_after_failure)
    with pytest.raises(QuestionBankABAuditError):
        await runner.run_pilot()
    assert provider.go_attempts == 1
    manifest = json.loads(runner.manifest_path.read_text(encoding="utf-8"))
    assert manifest["provider_attempts"][-1]["failure_category"] == "rate_limit"
    assert not runner.lock_path.exists()
    _assert_no_sensitive_files(config.run_dir)


@pytest.mark.asyncio
async def test_cancellation_is_checkpointed_without_inventing_read_timeout(tmp_path):
    class CancelProvider(PairedFakeProvider):
        async def generate_json(self, request):
            raise asyncio.CancelledError(SENSITIVE)

    runner = QuestionBankABRunner(llm_client=CancelProvider(), config=_config(tmp_path))
    with pytest.raises(asyncio.CancelledError):
        await runner.run_smoke()
    report = json.loads(runner.report_json_path.read_text(encoding="utf-8"))
    assert report["provider_attempts"][0]["status"] == "cancelled"
    assert report["provider_attempts"][0]["failure_category"] == "unknown_provider"
    _assert_no_sensitive_files(runner.config.run_dir)


def test_hard_process_exit_keeps_first_failure_and_inflight_attempt(tmp_path):
    # A subprocess uses only local fakes; os._exit skips every Python finally block.
    worker = tmp_path / "crash_worker.py"
    worker.write_text('''
import asyncio, os, socket, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from app.services.question_bank_ab_service import QuestionBankABRunner, QuestionBankABConfig
from tests.integration.test_question_bank_ab_provider_observability import _http_error

original_connect = socket.socket.connect
original_connect_ex = socket.socket.connect_ex
original_create = socket.create_connection
def loopback(address):
    return isinstance(address, tuple) and str(address[0]) in ("127.0.0.1", "::1", "localhost")
def blocked_connect(sock, address):
    if loopback(address):
        return original_connect(sock, address)
    raise AssertionError("subprocess network forbidden")
def blocked_connect_ex(sock, address):
    if loopback(address):
        return original_connect_ex(sock, address)
    raise AssertionError("subprocess network forbidden")
def blocked_create(address, *args, **kwargs):
    if loopback(address):
        return original_create(address, *args, **kwargs)
    raise AssertionError("subprocess network forbidden")
socket.socket.connect = blocked_connect
socket.socket.connect_ex = blocked_connect_ex
socket.create_connection = blocked_create

class CrashProvider:
    provider = "deepseek"
    model_name = "offline-crash"
    calls = 0
    async def generate_json(self, request):
        self.calls += 1
        if self.calls == 2:
            os._exit(23)
        raise _http_error()

async def main():
    runner = QuestionBankABRunner(llm_client=CrashProvider(), config=QuestionBankABConfig(
        input_path=Path("tests/fixtures/question_bank_ab_inputs_v1.json"),
        run_dir=Path(sys.argv[1]), lock_path=Path(sys.argv[1]) / ".lock"))
    runner._load_or_initialize()
    await runner._execute_variant(case=runner._cases[0], pair=1, variant="candidate", execution_order=2)
asyncio.run(main())
''', encoding="utf-8")
    run_dir = tmp_path / "offline-crash"
    result = subprocess.run(
        [sys.executable, str(worker), str(run_dir)], capture_output=True, text=True,
        timeout=20, env={**os.environ, "RUN_REAL_LLM_ACCEPTANCE": "false", "RUN_REAL_LLM_SMOKE_TESTS": "0"},
    )
    assert result.returncode == 23
    for name in ("manifest.json", "question-bank-ab-report.json"):
        data = json.loads((run_dir / name).read_text(encoding="utf-8"))
        assert [row["status"] for row in data["provider_attempts"]] == ["failed", "started"]
        assert data["provider_attempts"][0]["failure_category"] == "rate_limit"
        assert data["provider_attempts"][0]["attempt"] == 1
        assert data["budget"]["total_tokens_used"] is None
        assert data["runs"] == []
    assert "rate_limit" in (run_dir / "question-bank-ab-report.md").read_text(encoding="utf-8")
    _assert_no_sensitive_files(run_dir)
    provider = PairedFakeProvider()
    provider.model_name = "offline-crash"
    runner = QuestionBankABRunner(llm_client=provider, config=QuestionBankABConfig(
        input_path=Path("tests/fixtures/question_bank_ab_inputs_v1.json"),
        run_dir=run_dir, lock_path=run_dir / ".lock",
    ))
    runner._load_or_initialize()
    recovered = json.loads(runner.report_json_path.read_text(encoding="utf-8"))
    assert recovered["status"] == "incomplete_interrupted"
    assert provider.requests == []
