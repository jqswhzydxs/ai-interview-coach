import hashlib
import json
from pathlib import Path

import httpx
import pytest

from app.agents.llm_client import LLMResponse, TokenUsage
from app.agents.question_bank_agent import QuestionBankAgent
from app.agents.question_draft_prompt_experiment import PROMPT_ASSETS
from app.services import prep_package_service
from app.services.question_draft_provider_readiness_v2 import (
    QuestionDraftProviderReadinessV2Config,
    QuestionDraftProviderReadinessV2Runner,
)
from app.services.question_draft_token_experiment import (
    PROTOCOL_VERSION as PROTOCOL_V1,
)
from app.services.question_draft_token_experiment_v2 import (
    QuestionDraftTokenExperimentV2BudgetError,
    QuestionDraftTokenExperimentV2Config,
    QuestionDraftTokenExperimentV2ProtocolError,
    QuestionDraftTokenExperimentV2Runner,
)
from app.services.question_draft_token_protocol_v2 import PROTOCOL_VERSION
from tests.unit.test_question_bank_draft_protocol import _valid_draft


PROJECT_ROOT = Path(__file__).resolve().parents[2]
B2_BASELINE = (
    PROJECT_ROOT
    / "storage/reports/question-bank-token-phase-2-4d-b2-offline-20261022"
    / "protected-assets-before.json"
)


class ScriptedProvider:
    provider = "offline-v2-provider"
    model_name = "frozen-v2-model"

    def __init__(self, *, failure_calls=None, timeout_calls=None, missing_usage_calls=None):
        self.failure_calls = set(failure_calls or ())
        self.timeout_calls = set(timeout_calls or ())
        self.missing_usage_calls = set(missing_usage_calls or ())
        self.calls = 0
        self.requests = []

    async def generate_json(self, request):
        self.calls += 1
        self.requests.append(request)
        if self.calls in self.timeout_calls:
            raise httpx.ReadTimeout(
                "offline timeout",
                request=httpx.Request("POST", "https://provider.invalid"),
            )
        if self.calls in self.failure_calls:
            raise httpx.RemoteProtocolError(
                "offline remote protocol error",
                request=httpx.Request("POST", "https://provider.invalid"),
            )
        input_data = json.loads(request.user_prompt)
        technology = input_data["resume_profile"]["skills"][0]
        candidate = (
            PROMPT_ASSETS["candidate"].path.read_text(encoding="utf-8")
            in request.system_prompt
        )
        output_tokens = 1_600 if candidate else 2_000
        usage = (
            None
            if self.calls in self.missing_usage_calls
            else TokenUsage(
                input_tokens=400,
                output_tokens=output_tokens,
                total_tokens=400 + output_tokens,
            )
        )
        return LLMResponse(
            provider=self.provider,
            model_name=self.model_name,
            content=_valid_draft(technology),
            usage=usage,
            raw_text="RAW_AB_RESPONSE_MUST_NOT_BE_PERSISTED",
        )


async def passed_readiness(tmp_path, *, provider=None):
    client = provider or ScriptedProvider()
    ledger = tmp_path / "readiness-v2.json"
    readiness = QuestionDraftProviderReadinessV2Runner(
        llm_client=client,
        config=QuestionDraftProviderReadinessV2Config(ledger_path=ledger),
    )
    readiness.prepare()
    result = await readiness.attempt()
    assert result.ledger["status"] == "passed"
    return ledger, client


def v2_runner(tmp_path, provider, ledger, *, run_name="v2-ab"):
    return QuestionDraftTokenExperimentV2Runner(
        llm_client=provider,
        config=QuestionDraftTokenExperimentV2Config(
            run_dir=tmp_path / run_name,
            readiness_ledger_path=ledger,
            lock_path=tmp_path / f".{run_name}.lock",
        ),
    )


@pytest.mark.asyncio
async def test_readiness_must_pass_before_ab_directory_is_created(tmp_path):
    provider = ScriptedProvider()
    ledger = tmp_path / "readiness-v2.json"
    readiness = QuestionDraftProviderReadinessV2Runner(
        llm_client=provider,
        config=QuestionDraftProviderReadinessV2Config(ledger_path=ledger),
    )
    readiness.prepare()
    run_dir = tmp_path / "must-not-exist"
    with pytest.raises(
        QuestionDraftTokenExperimentV2ProtocolError,
        match="matching passed readiness ledger",
    ):
        QuestionDraftTokenExperimentV2Runner(
            llm_client=provider,
            config=QuestionDraftTokenExperimentV2Config(
                run_dir=run_dir,
                readiness_ledger_path=ledger,
            ),
        )
    assert not run_dir.exists()
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_provider_model_and_asset_drift_are_rejected_before_directory_creation(tmp_path):
    ledger, readiness_provider = await passed_readiness(tmp_path)
    mismatched = ScriptedProvider()
    mismatched.model_name = "different-model"
    mismatch_dir = tmp_path / "model-mismatch"
    with pytest.raises(QuestionDraftTokenExperimentV2ProtocolError):
        v2_runner(tmp_path, mismatched, ledger, run_name="model-mismatch")
    assert not mismatch_dir.exists()

    payload = json.loads(ledger.read_text(encoding="utf-8"))
    payload["assets"]["prompt"]["sha256"] = "0" * 64
    ledger.write_text(json.dumps(payload), encoding="utf-8")
    drift_dir = tmp_path / "asset-drift"
    with pytest.raises(QuestionDraftTokenExperimentV2ProtocolError):
        v2_runner(tmp_path, readiness_provider, ledger, run_name="asset-drift")
    assert not drift_dir.exists()


@pytest.mark.asyncio
async def test_manifest_binds_readiness_hash_and_later_ledger_change_is_rejected(tmp_path):
    ledger, provider = await passed_readiness(tmp_path)
    runner = v2_runner(tmp_path, provider, ledger)
    report = runner.prepare().report
    expected_hash = hashlib.sha256(ledger.read_bytes()).hexdigest()
    assert report["readiness"]["sha256"] == expected_hash
    manifest = json.loads(runner.manifest_path.read_text(encoding="utf-8"))
    assert manifest["readiness"]["sha256"] == expected_hash

    payload = json.loads(ledger.read_text(encoding="utf-8"))
    payload["post_pass_mutation"] = True
    ledger.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(
        QuestionDraftTokenExperimentV2ProtocolError,
        match="ledger hash drift",
    ):
        runner.prepare()


@pytest.mark.asyncio
async def test_timeout_then_success_uses_success_usage_and_marks_billing_incomplete(tmp_path):
    ledger, _ = await passed_readiness(tmp_path, provider=ScriptedProvider())
    provider = ScriptedProvider(timeout_calls={1})
    runner = v2_runner(tmp_path, provider, ledger)
    report = (await runner.run_smoke()).report
    smoke = report["smoke"]
    assert report["status"] == "smoke_passed"
    assert provider.calls == 2
    assert smoke["execution_mode"] == "real"
    assert smoke["successful_response_usage"]["output_tokens"] == 1_600
    assert smoke["successful_response_usage"]["status"] == "complete"
    assert smoke["billing_usage_completeness"]["status"] == "incomplete"
    assert smoke["known_token_lower_bound"]["total_tokens"] == 2_000
    assert smoke["execution_reliability"]["timeout_attempts"] == 1
    assert smoke["retry_count"] == 1


@pytest.mark.asyncio
async def test_two_remote_protocol_errors_fallback_is_excluded(tmp_path):
    ledger, _ = await passed_readiness(tmp_path, provider=ScriptedProvider())
    provider = ScriptedProvider(failure_calls={1, 2})
    runner = v2_runner(tmp_path, provider, ledger)
    report = (await runner.run_smoke()).report
    smoke = report["smoke"]
    assert report["status"] == "smoke_failed"
    assert smoke["execution_mode"] == "fallback"
    assert smoke["execution_reliability"]["network_error_attempts"] == 2
    assert smoke["execution_reliability"]["fallback_used"] is True
    assert smoke["successful_response_usage"]["status"] == "not_applicable"
    assert smoke["output_tokens"] is None
    assert smoke["known_token_lower_bound"]["total_tokens"] is None


@pytest.mark.asyncio
async def test_fallback_never_enters_token_or_blind_quality_comparison(tmp_path):
    ledger, _ = await passed_readiness(tmp_path, provider=ScriptedProvider())
    # Call 1 is smoke. Calls 2 and 3 exhaust the Go baseline and produce fallback.
    provider = ScriptedProvider(failure_calls={2, 3})
    runner = v2_runner(tmp_path, provider, ledger)
    assert (await runner.run_smoke()).report["status"] == "smoke_passed"
    report = (await runner.run_pilot()).report
    assert report["status"] == "pilot_passed"
    assert report["summary"]["token_comparison"]["comparable_pair_count"] == 2
    reasons = report["summary"]["token_comparison"]["excluded_pair_reasons"]
    assert reasons["baseline_final_output_not_real"] == 1
    packet = json.loads(runner.blind_packet_path.read_text(encoding="utf-8"))
    assert len(packet["submissions"]) == 5
    fallback = next(
        run
        for run in report["runs"]
        if run["case_id"] == "backend_go_case" and run["variant"] == "baseline"
    )
    assert fallback["execution_mode"] == "fallback"
    assert fallback["submission_id"] is None


@pytest.mark.asyncio
async def test_full_offline_v2_runner_has_fifteen_comparable_pairs_and_is_idempotent(tmp_path):
    ledger, _ = await passed_readiness(tmp_path, provider=ScriptedProvider())
    provider = ScriptedProvider()
    runner = v2_runner(tmp_path, provider, ledger)
    assert runner.prepare().report["budget"]["provider_call_budget"]["used"] == 0
    assert (await runner.run_smoke()).report["status"] == "smoke_passed"
    assert (await runner.run_pilot()).report["status"] == "pilot_passed"
    report = (await runner.run_full()).report
    comparison = report["summary"]["token_comparison"]
    assert report["status"] == "execution_completed"
    assert comparison["status"] == "evaluated"
    assert comparison["comparable_pair_count"] == 15
    assert comparison["baseline_output_tokens"] == 30_000
    assert comparison["candidate_output_tokens"] == 24_000
    assert comparison["candidate_average_output_tokens"] == 1_600
    assert comparison["paired_output_token_reduction"] == 0.2
    assert report["budget"]["provider_call_budget"]["used"] == 31
    assert report["budget"]["total_token_budget_policy"] == "known_lower_bound_audit"
    assert report["budget"]["total_token_budget_is_hard_gate"] is False
    assert all(run["metadata_assembler_version"] == "deterministic-metadata-v2" for run in report["runs"])
    assert all(run["max_tokens"] is None and run["temperature"] == 0.2 for run in report["runs"])
    assert len(json.loads(runner.blind_packet_path.read_text(encoding="utf-8"))["submissions"]) == 30
    calls_before = provider.calls
    second = await runner.run_full()
    assert second.report == report
    assert provider.calls == calls_before == 31
    assert "RAW_AB_RESPONSE_MUST_NOT_BE_PERSISTED" not in runner.audit_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_call_budget_hard_stops_before_provider_call(tmp_path):
    ledger, _ = await passed_readiness(tmp_path, provider=ScriptedProvider())
    provider = ScriptedProvider()
    runner = v2_runner(tmp_path, provider, ledger)
    runner._manifest["provider_calls"] = [
        {
            "call": index,
            "status": "failed",
            "token_usage": {"input_tokens": None, "output_tokens": None, "total_tokens": None},
        }
        for index in range(1, 62)
    ]
    with pytest.raises(QuestionDraftTokenExperimentV2BudgetError):
        await runner.run_smoke()
    assert provider.calls == 0


def test_protocol_v1_and_frozen_assets_remain_unchanged():
    assert PROTOCOL_V1 == "phase-2.4d-question-draft-prompt-token-v1"
    assert PROTOCOL_VERSION == "phase-2.4d-question-draft-prompt-token-v2"
    baseline = json.loads(B2_BASELINE.read_text(encoding="utf-8"))
    assert baseline["file_count"] == 129
    changed = []
    for relative, expected in baseline["files"].items():
        path = PROJECT_ROOT / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if actual != expected:
            changed.append(relative)
    assert changed == []
    assert prep_package_service.QuestionBankAgent is QuestionBankAgent
    assert QuestionBankAgent.prompt_version == "question_bank_agent_v0.1"
