import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.agents.deepseek_thinking_experiment_client import (
    DeepSeekThinkingExperimentResponse,
    WhitelistedUsageDetails,
)
from app.agents.llm_client import TokenUsage
from app.agents.question_bank_agent import QuestionBankAgent
from app.services import prep_package_service
from app.services.phase_2_4d_b_protocol_review import verify_protected_assets
from app.services.question_draft_provider_readiness_v3 import (
    QuestionDraftProviderReadinessV3Config,
    QuestionDraftProviderReadinessV3Runner,
)
from app.services.question_draft_reasoning_experiment_v3 import (
    QuestionDraftReasoningExperimentV3BudgetError,
    QuestionDraftReasoningExperimentV3Config,
    QuestionDraftReasoningExperimentV3ProtocolError,
    QuestionDraftReasoningExperimentV3Runner,
)
from scripts.run_question_draft_reasoning_experiment_v3 import (
    require_real_ab_authorization,
)
from tests.unit.test_question_bank_draft_protocol import _valid_draft


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTECTED_BASELINE = (
    PROJECT_ROOT
    / "storage/reports/question-bank-token-phase-2-4d-d-a-offline-20261023"
    / "protected-assets-before.json"
)


class ReasoningClient:
    provider = "deepseek"
    model_name = "deepseek-v4-pro"
    base_url = "https://provider.invalid"
    api_key = "offline-only"

    def __init__(self, thinking_type, *, failure_calls=None, timeout_calls=None, missing_usage_calls=None):
        self.thinking_type = thinking_type
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
                "offline protocol error",
                request=httpx.Request("POST", "https://provider.invalid"),
            )
        input_data = json.loads(request.user_prompt)
        technology = input_data["resume_profile"]["skills"][0]
        output_tokens = 2_200 if self.thinking_type == "enabled" else 1_600
        usage = (
            None
            if self.calls in self.missing_usage_calls
            else TokenUsage(
                input_tokens=500,
                output_tokens=output_tokens,
                total_tokens=500 + output_tokens,
            )
        )
        details = WhitelistedUsageDetails(
            reasoning_tokens=600 if self.thinking_type == "enabled" else 0,
            visible_completion_tokens=1_600,
            cached_input_tokens=100,
        )
        return DeepSeekThinkingExperimentResponse(
            provider=self.provider,
            model_name=self.model_name,
            content=_valid_draft(technology),
            usage=usage,
            usage_details=details,
            raw_text="RAW_AB_RESPONSE_MUST_NOT_BE_PERSISTED",
        )


def client_pair(**candidate_kwargs):
    return {
        "baseline": ReasoningClient("enabled"),
        "candidate": ReasoningClient("disabled", **candidate_kwargs),
    }


async def passed_readiness(tmp_path):
    client = ReasoningClient("disabled")
    ledger = tmp_path / "readiness-v3.json"
    readiness = QuestionDraftProviderReadinessV3Runner(
        llm_client=client,
        config=QuestionDraftProviderReadinessV3Config(ledger_path=ledger),
    )
    readiness.prepare()
    assert (await readiness.attempt()).ledger["status"] == "passed"
    return ledger


def make_runner(tmp_path, clients, ledger, *, name="reasoning-v3"):
    return QuestionDraftReasoningExperimentV3Runner(
        llm_clients=clients,
        config=QuestionDraftReasoningExperimentV3Config(
            run_dir=tmp_path / name,
            readiness_ledger_path=ledger,
            lock_path=tmp_path / f".{name}.lock",
        ),
    )


def test_readiness_must_pass_before_ab_directory_is_created(tmp_path):
    client = ReasoningClient("disabled")
    ledger = tmp_path / "pending-readiness-v3.json"
    readiness = QuestionDraftProviderReadinessV3Runner(
        llm_client=client,
        config=QuestionDraftProviderReadinessV3Config(ledger_path=ledger),
    )
    readiness.prepare()
    run_dir = tmp_path / "must-not-exist"
    with pytest.raises(QuestionDraftReasoningExperimentV3ProtocolError, match="passed readiness"):
        make_runner(tmp_path, client_pair(), ledger, name="must-not-exist")
    assert not run_dir.exists()


@pytest.mark.asyncio
async def test_provider_model_and_thinking_drift_are_rejected(tmp_path):
    ledger = await passed_readiness(tmp_path)
    for variant, attribute, value in (
        ("baseline", "thinking_type", "disabled"),
        ("candidate", "thinking_type", "enabled"),
        ("candidate", "model_name", "deepseek-chat"),
        ("candidate", "provider", "kimi"),
        ("candidate", "base_url", "https://different.invalid"),
    ):
        clients = client_pair()
        setattr(clients[variant], attribute, value)
        with pytest.raises(QuestionDraftReasoningExperimentV3ProtocolError):
            make_runner(tmp_path, clients, ledger, name=f"drift-{variant}-{attribute}")
        assert not (tmp_path / f"drift-{variant}-{attribute}").exists()


@pytest.mark.asyncio
async def test_full_offline_v3_has_fifteen_pairs_single_variable_and_usage_details(tmp_path):
    ledger = await passed_readiness(tmp_path)
    clients = client_pair()
    runner = make_runner(tmp_path, clients, ledger)
    prepared = runner.prepare().report
    assert prepared["protocol"]["unique_variable"] == "thinking.type"
    assert prepared["prompt_assets"]["baseline"] == prepared["prompt_assets"]["candidate"]
    assert (await runner.run_smoke()).report["status"] == "smoke_passed"
    assert (await runner.run_pilot()).report["status"] == "pilot_passed"
    report = (await runner.run_full()).report
    assert report["status"] == "execution_completed"
    assert report["summary"]["run_count"] == 30
    comparison = report["summary"]["token_comparison"]
    assert comparison["comparable_pair_count"] == 15
    assert comparison["baseline_output_tokens"] == 33_000
    assert comparison["candidate_output_tokens"] == 24_000
    assert comparison["candidate_average_output_tokens"] == 1_600
    assert comparison["paired_output_token_reduction"] == pytest.approx(9_000 / 33_000)
    assert report["thresholds"]["gates"]["candidate_15_of_15_real_safe"]["status"] == "pass"
    assert report["thresholds"]["gates"]["fallback_count_eq_0"]["status"] == "pass"
    assert report["thresholds"]["verdict"] == "pending"
    assert report["budget"]["provider_call_budget"]["used"] == 31
    for run in report["runs"]:
        assert run["prompt_version"] == "question_bank_draft_agent_v0.2"
        assert run["thinking"] == {"type": "enabled" if run["variant"] == "baseline" else "disabled"}
        assert run["reasoning_effort_present"] is False
        assert run["successful_response_usage_details"]["visible_completion_tokens"] == {
            "status": "available",
            "value": 1_600,
        }
    for case in {run["case_id"] for run in report["runs"]}:
        for pair in range(1, 6):
            selected = [run for run in report["runs"] if run["case_id"] == case and run["pair"] == pair]
            assert [run["variant"] for run in sorted(selected, key=lambda row: row["execution_order"])] == (
                ["baseline", "candidate"] if pair % 2 else ["candidate", "baseline"]
            )
            assert len({run["request_invariant_sha256"] for run in selected}) == 1
    packet = json.loads(runner.blind_packet_path.read_text(encoding="utf-8"))
    assert len(packet["submissions"]) == 30
    assert all("variant" not in row for row in packet["submissions"])
    persisted = runner.audit_path.read_text(encoding="utf-8")
    assert "RAW_AB_RESPONSE_MUST_NOT_BE_PERSISTED" not in persisted
    assert "reasoning_content" not in persisted


@pytest.mark.asyncio
async def test_fallback_is_excluded_and_timeout_success_has_incomplete_billing(tmp_path):
    ledger = await passed_readiness(tmp_path)
    clients = {
        "baseline": ReasoningClient("enabled", failure_calls={1, 2}),
        "candidate": ReasoningClient("disabled", timeout_calls={2}),
    }
    runner = make_runner(tmp_path, clients, ledger)
    assert (await runner.run_smoke()).report["status"] == "smoke_passed"
    report = (await runner.run_pilot()).report
    go_baseline = next(
        run for run in report["runs"]
        if run["case_id"] == "backend_go_case" and run["variant"] == "baseline"
    )
    go_candidate = next(
        run for run in report["runs"]
        if run["case_id"] == "backend_go_case" and run["variant"] == "candidate"
    )
    assert go_baseline["execution_mode"] == "fallback"
    assert go_baseline["submission_id"] is None
    assert go_candidate["execution_mode"] == "real"
    assert go_candidate["retry_count"] == 1
    assert go_candidate["billing_usage_completeness"]["status"] == "incomplete"
    assert go_candidate["successful_response_usage"]["output_tokens"] == 1_600
    assert report["summary"]["token_comparison"]["comparable_pair_count"] == 2
    packet = json.loads(runner.blind_packet_path.read_text(encoding="utf-8"))
    assert len(packet["submissions"]) == 5


@pytest.mark.asyncio
async def test_call_budget_hard_stops_before_provider_call(tmp_path):
    ledger = await passed_readiness(tmp_path)
    clients = client_pair()
    runner = make_runner(tmp_path, clients, ledger)
    runner._manifest["provider_calls"] = [
        {
            "call": index,
            "status": "failed",
            "token_usage": {"input_tokens": None, "output_tokens": None, "total_tokens": None},
        }
        for index in range(1, 62)
    ]
    with pytest.raises(QuestionDraftReasoningExperimentV3BudgetError):
        await runner.run_smoke()
    assert clients["candidate"].calls == 0


@pytest.mark.parametrize("phase", ["smoke", "pilot", "full"])
def test_each_real_phase_requires_its_own_explicit_authorization(phase):
    args = SimpleNamespace(
        authorize_phase_2_4d_d_a_smoke=False,
        authorize_phase_2_4d_d_a_pilot=False,
        authorize_phase_2_4d_d_a_full=False,
    )
    settings = SimpleNamespace(
        run_real_llm_acceptance=True,
        save_full_llm_logs=False,
        llm_provider="deepseek",
        llm_model="deepseek-v4-pro",
        deepseek_api_key="offline-only",
    )
    with pytest.raises(SystemExit, match=f"authorize-phase-2-4d-d-a-{phase}"):
        require_real_ab_authorization(args, settings, phase)


def test_frozen_assets_and_production_default_remain_unchanged():
    result = verify_protected_assets(PROTECTED_BASELINE)
    assert result["status"] == "passed"
    assert result["checked_file_count"] == 161
    assert result["missing"] == []
    assert result["changed"] == []
    assert prep_package_service.QuestionBankAgent is QuestionBankAgent
    assert QuestionBankAgent.prompt_version == "question_bank_agent_v0.1"
