import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from app.agents.deepseek_reasoning_effort_experiment_client import (
    DeepSeekReasoningEffortExperimentResponse,
    WhitelistedUsageDetails,
)
from app.agents.llm_client import TokenUsage
from app.agents.question_bank_agent import QuestionBankAgent
from app.services import prep_package_service
from app.services.phase_2_4d_b_protocol_review import verify_protected_assets
from app.services.question_draft_provider_readiness_v4 import (
    QuestionDraftProviderReadinessV4Config,
    QuestionDraftProviderReadinessV4Runner,
)
from app.services.question_draft_reasoning_effort_experiment_v4 import (
    QuestionDraftReasoningExperimentV4BudgetError,
    QuestionDraftReasoningExperimentV4Config,
    QuestionDraftReasoningExperimentV4ProtocolError,
    QuestionDraftReasoningExperimentV4Runner,
)
from scripts.run_question_draft_reasoning_effort_experiment_v4 import (
    require_real_ab_authorization,
)
from tests.unit.test_question_bank_draft_protocol import _valid_draft


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTECTED_BASELINE = (
    PROJECT_ROOT
    / "storage/reports/question-bank-token-phase-2-4d-e-a-offline-20261023"
    / "protected-assets-before.json"
)


class ReasoningClient:
    provider = "deepseek"
    model_name = "deepseek-v4-pro"
    base_url = "https://provider.invalid"
    api_key = "offline-only"

    def __init__(self, reasoning_effort, *, failure_calls=None, timeout_calls=None, missing_usage_calls=None):
        self.thinking_type = "enabled"
        self.reasoning_effort = reasoning_effort
        self.failure_calls = set(failure_calls or ())
        self.timeout_calls = set(timeout_calls or ())
        self.missing_usage_calls = set(missing_usage_calls or ())
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
            "thinking": {"type": "enabled"},
            "reasoning_effort": self.reasoning_effort,
        }

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
        output_tokens = 2_200 if self.reasoning_effort == "high" else 1_600
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
            reasoning_tokens=600 if self.reasoning_effort == "high" else 300,
            visible_completion_tokens=1_600,
            cached_input_tokens=100,
        )
        return DeepSeekReasoningEffortExperimentResponse(
            provider=self.provider,
            model_name=self.model_name,
            content=_valid_draft(technology),
            usage=usage,
            usage_details=details,
            raw_text="RAW_AB_RESPONSE_MUST_NOT_BE_PERSISTED",
        )


def client_pair(**candidate_kwargs):
    return {
        "baseline": ReasoningClient("high"),
        "candidate": ReasoningClient("low", **candidate_kwargs),
    }


async def passed_readiness(tmp_path):
    client = ReasoningClient("low")
    ledger = tmp_path / "readiness-v4.json"
    readiness = QuestionDraftProviderReadinessV4Runner(
        llm_client=client,
        config=QuestionDraftProviderReadinessV4Config(ledger_path=ledger),
    )
    readiness.prepare()
    assert (await readiness.attempt()).ledger["status"] == "passed"
    return ledger


def make_runner(tmp_path, clients, ledger, *, name="reasoning-v4"):
    return QuestionDraftReasoningExperimentV4Runner(
        llm_clients=clients,
        config=QuestionDraftReasoningExperimentV4Config(
            run_dir=tmp_path / name,
            readiness_ledger_path=ledger,
            lock_path=tmp_path / f".{name}.lock",
        ),
    )


def test_readiness_must_pass_before_ab_directory_is_created(tmp_path):
    client = ReasoningClient("low")
    ledger = tmp_path / "pending-readiness-v4.json"
    readiness = QuestionDraftProviderReadinessV4Runner(
        llm_client=client,
        config=QuestionDraftProviderReadinessV4Config(ledger_path=ledger),
    )
    readiness.prepare()
    run_dir = tmp_path / "must-not-exist"
    with pytest.raises(QuestionDraftReasoningExperimentV4ProtocolError, match="passed readiness"):
        make_runner(tmp_path, client_pair(), ledger, name="must-not-exist")
    assert not run_dir.exists()


@pytest.mark.asyncio
async def test_provider_model_and_request_control_drift_are_rejected(tmp_path):
    ledger = await passed_readiness(tmp_path)
    for variant, attribute, value in (
        ("baseline", "thinking_type", "disabled"),
        ("candidate", "reasoning_effort", "high"),
        ("candidate", "model_name", "deepseek-chat"),
        ("candidate", "provider", "kimi"),
        ("candidate", "base_url", "https://different.invalid"),
    ):
        clients = client_pair()
        setattr(clients[variant], attribute, value)
        with pytest.raises(QuestionDraftReasoningExperimentV4ProtocolError):
            make_runner(tmp_path, clients, ledger, name=f"drift-{variant}-{attribute}")
        assert not (tmp_path / f"drift-{variant}-{attribute}").exists()


@pytest.mark.asyncio
async def test_full_offline_v4_has_fifteen_pairs_single_variable_and_usage_details(tmp_path):
    ledger = await passed_readiness(tmp_path)
    clients = client_pair()
    runner = make_runner(tmp_path, clients, ledger)
    prepared = runner.prepare().report
    assert prepared["protocol"]["unique_variable"] == "reasoning_effort"
    assert prepared["protocol"]["historical_v3_samples_reused"] is False
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
        assert run["thinking"] == {"type": "enabled"}
        assert run["reasoning_effort"] == (
            "high" if run["variant"] == "baseline" else "low"
        )
        assert run["reasoning_effort_present"] is True
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
            assert len({run["provider_request_sha256"] for run in selected}) == 2
    packet = json.loads(runner.blind_packet_path.read_text(encoding="utf-8"))
    assert len(packet["submissions"]) == 30
    assert all("variant" not in row for row in packet["submissions"])
    assert len({row["submission_id"] for row in packet["submissions"]}) == 30
    private_map = json.loads(runner.private_map_path.read_text(encoding="utf-8"))
    assert len(private_map["mapping"]) == 30
    persisted = runner.audit_path.read_text(encoding="utf-8")
    assert "RAW_AB_RESPONSE_MUST_NOT_BE_PERSISTED" not in persisted
    assert "reasoning_content" not in persisted
    assert '"resume_profile"' not in persisted
    assert '"job_description"' not in persisted
    manifest_text = runner.manifest_path.read_text(encoding="utf-8")
    assert '"resume_profile"' not in manifest_text
    assert '"job_description"' not in manifest_text

    template = json.loads(runner.review_template_path.read_text(encoding="utf-8"))
    template["evaluator"] = {
        "type": "AI",
        "identifier": "offline-independent-reviewer",
        "independence_confirmed": True,
    }
    for submission in template["submissions"]:
        submission["text_scores"] = {
            dimension: 4 for dimension in submission["text_scores"]
        }
        submission["metadata_fit_scores"] = [4] * 25
    incomplete_path = tmp_path / "incomplete-review.json"
    incomplete = json.loads(json.dumps(template))
    incomplete["submissions"].pop()
    incomplete_path.write_text(json.dumps(incomplete), encoding="utf-8")
    with pytest.raises(
        QuestionDraftReasoningExperimentV4ProtocolError,
        match="IDs or order",
    ):
        runner.apply_blind_review(incomplete_path)
    review_path = tmp_path / "complete-review.json"
    review_path.write_text(json.dumps(template), encoding="utf-8")
    finalized = runner.apply_blind_review(review_path).report
    assert finalized["status"] == "completed"
    assert finalized["thresholds"]["verdict"] == "pass"
    assert runner._manifest["review"]["score_counts"] == {
        "text_dimension_scores": 150,
        "metadata_fit_scores": 750,
    }


@pytest.mark.asyncio
async def test_fallback_is_excluded_and_timeout_success_has_incomplete_billing(tmp_path):
    ledger = await passed_readiness(tmp_path)
    clients = {
        "baseline": ReasoningClient("high", failure_calls={1, 2}),
        "candidate": ReasoningClient("low", timeout_calls={2}),
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
    with pytest.raises(QuestionDraftReasoningExperimentV4BudgetError):
        await runner.run_smoke()
    assert clients["candidate"].calls == 0


@pytest.mark.parametrize("phase", ["smoke", "pilot", "full"])
def test_each_real_phase_requires_its_own_explicit_authorization(phase):
    args = SimpleNamespace(
        authorize_phase_2_4d_e_a_smoke=False,
        authorize_phase_2_4d_e_a_pilot=False,
        authorize_phase_2_4d_e_a_full=False,
    )
    settings = SimpleNamespace(
        run_real_llm_acceptance=True,
        save_full_llm_logs=False,
        llm_provider="deepseek",
        llm_model="deepseek-v4-pro",
        deepseek_api_key="offline-only",
    )
    with pytest.raises(SystemExit, match=f"authorize-phase-2-4d-e-a-{phase}"):
        require_real_ab_authorization(args, settings, phase)


def test_frozen_assets_and_production_default_remain_unchanged():
    result = verify_protected_assets(PROTECTED_BASELINE)
    assert result["status"] == "passed"
    assert result["checked_file_count"] == 203
    assert result["missing"] == []
    assert result["changed"] == []
    assert prep_package_service.QuestionBankAgent is QuestionBankAgent
    assert QuestionBankAgent.prompt_version == "question_bank_agent_v0.1"
