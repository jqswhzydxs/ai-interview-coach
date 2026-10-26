import asyncio
import json
from pathlib import Path

import pytest

from app.agents.llm_client import LLMRequest, LLMResponse, TokenUsage
from app.agents.mock_client import MockLLMClient
from app.agents.question_bank_agent import QuestionBankAgent
from app.services.question_bank_ab_service import (
    DEFAULT_ASSET_PATHS,
    QuestionBankABConfig,
    QuestionBankABLockError,
    QuestionBankABProtocolError,
    QuestionBankABRunner,
)
from tests.unit.test_question_bank_draft_protocol import _valid_draft


INPUT_PATH = Path("tests/fixtures/question_bank_ab_inputs_v1.json")


class PairedFakeProvider:
    provider = "deepseek"
    model_name = "fake-paired-model"

    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    async def generate_json(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if request.response_schema_name == "ProviderSmoke":
            content = {"status": "ok"}
            usage = TokenUsage(input_tokens=5, output_tokens=2, total_tokens=7)
        elif request.response_schema_name == "QuestionBank":
            input_data = json.loads(request.user_prompt)
            content = QuestionBankAgent(
                MockLLMClient()
            )._rule_based_question_bank(input_data)
            usage = TokenUsage(input_tokens=30, output_tokens=100, total_tokens=130)
        elif request.response_schema_name == "QuestionDraftBank":
            input_data = json.loads(request.user_prompt)
            technology = input_data["resume_profile"]["skills"][0]
            content = _valid_draft(technology)
            usage = TokenUsage(input_tokens=20, output_tokens=40, total_tokens=60)
        else:
            raise AssertionError(
                f"QuestionBank A/B requested unexpected schema: {request.response_schema_name}"
            )
        return LLMResponse(
            provider=self.provider,
            model_name=self.model_name,
            content=content,
            usage=usage,
            raw_text="RAW_PROVIDER_RESPONSE_MUST_NOT_BE_SAVED",
        )


class SmokeThenHangingProvider(PairedFakeProvider):
    def __init__(self) -> None:
        super().__init__()
        self.cancelled = False

    async def generate_json(self, request: LLMRequest) -> LLMResponse:
        if request.response_schema_name == "ProviderSmoke":
            return await super().generate_json(request)
        self.requests.append(request)
        try:
            await asyncio.Event().wait()
        finally:
            self.cancelled = True


class SelectiveHangingProvider(PairedFakeProvider):
    def __init__(self, hanging_schema: str) -> None:
        super().__init__()
        self.hanging_schema = hanging_schema
        self.cancelled_count = 0

    async def generate_json(self, request: LLMRequest) -> LLMResponse:
        if request.response_schema_name != self.hanging_schema:
            return await super().generate_json(request)
        self.requests.append(request)
        try:
            await asyncio.Event().wait()
        finally:
            self.cancelled_count += 1


class GoBaselineHangingProvider(SelectiveHangingProvider):
    def __init__(self) -> None:
        super().__init__("QuestionBank")

    async def generate_json(self, request: LLMRequest) -> LLMResponse:
        if request.response_schema_name == "QuestionBank":
            input_data = json.loads(request.user_prompt)
            if input_data["resume_profile"]["skills"][0] != "Go":
                return await PairedFakeProvider.generate_json(self, request)
        return await super().generate_json(request)


class BaselineHangingHighTokenCandidateProvider(SelectiveHangingProvider):
    def __init__(self) -> None:
        super().__init__("QuestionBank")

    async def generate_json(self, request: LLMRequest) -> LLMResponse:
        response = await super().generate_json(request)
        if request.response_schema_name == "QuestionDraftBank":
            return response.model_copy(
                update={
                    "usage": TokenUsage(
                        input_tokens=20,
                        output_tokens=1_801,
                        total_tokens=1_821,
                    )
                }
            )
        return response


class InvalidCandidateDraftProvider(PairedFakeProvider):
    async def generate_json(self, request: LLMRequest) -> LLMResponse:
        if request.response_schema_name != "QuestionDraftBank":
            return await super().generate_json(request)
        self.requests.append(request)
        return LLMResponse(
            provider=self.provider,
            model_name=self.model_name,
            content={"invalid": "draft"},
            usage=TokenUsage(input_tokens=20, output_tokens=5, total_tokens=25),
        )


def _config(tmp_path: Path, **overrides) -> QuestionBankABConfig:
    values = {
        "input_path": INPUT_PATH,
        "run_dir": tmp_path / "run",
        "lock_path": tmp_path / ".question-bank-ab.lock",
        "max_provider_calls": 61,
        "max_total_tokens": 250_000,
        "execution_deadline_seconds": 1.0,
    }
    values.update(overrides)
    return QuestionBankABConfig(**values)


def _complete_reviews(template_path: Path) -> Path:
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    for submission in payload["submissions"]:
        submission["text_scores"] = {
            key: 5 for key in submission["text_scores"]
        }
        submission["metadata_fit_scores"] = [4] * 25
    review_path = template_path.with_name("completed-blind-reviews.json")
    review_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return review_path


@pytest.mark.asyncio
async def test_full_paired_ab_calls_only_question_bank_and_applies_blind_reviews(
    tmp_path,
) -> None:
    provider = PairedFakeProvider()
    runner = QuestionBankABRunner(
        llm_client=provider,
        config=_config(tmp_path),
    )

    smoke = await runner.run_smoke()
    pilot = await runner.run_pilot()
    execution = await runner.run_full()

    assert smoke.report["smoke"]["status"] == "passed"
    assert pilot.report["pilot"]["status"] == "passed"
    assert pilot.report["summary"]["run_count"] == 6
    assert execution.report["status"] == "execution_completed"
    assert execution.report["completion_status"] == "awaiting_review"
    assert execution.report["summary"]["run_count"] == 30
    assert set(execution.report["asset_hashes"]) == {
        "assembler",
        "base_agent",
        "baseline_agent",
        "baseline_prompt",
        "candidate_agent",
        "candidate_prompt",
        "draft_schema",
        "final_schema",
    }
    assert len(provider.requests) == 31
    assert {request.response_schema_name for request in provider.requests} == {
        "ProviderSmoke",
        "QuestionBank",
        "QuestionDraftBank",
    }
    assert sum(
        request.response_schema_name == "QuestionBank" for request in provider.requests
    ) == 15
    assert sum(
        request.response_schema_name == "QuestionDraftBank"
        for request in provider.requests
    ) == 15

    runs = execution.report["runs"]
    assert all(run["variant"] == "baseline" for run in runs if run["pair"] % 2 and run["execution_order"] == 1)
    assert all(run["variant"] == "candidate" for run in runs if run["pair"] % 2 == 0 and run["execution_order"] == 1)
    assert sum(run["variant"] == "baseline" for run in runs) == 15
    assert sum(run["variant"] == "candidate" for run in runs) == 15
    for case_id in {
        "backend_go_case",
        "backend_java_case",
        "backend_python_case",
    }:
        assert sum(
            run["case_id"] == case_id and run["variant"] == "baseline"
            for run in runs
        ) == 5
        assert sum(
            run["case_id"] == case_id and run["variant"] == "candidate"
            for run in runs
        ) == 5
        for pair in range(1, 6):
            pair_order = [
                run["variant"]
                for run in sorted(
                    (
                        run
                        for run in runs
                        if run["case_id"] == case_id and run["pair"] == pair
                    ),
                    key=lambda run: run["execution_order"],
                )
            ]
            assert pair_order == (
                ["baseline", "candidate"]
                if pair % 2
                else ["candidate", "baseline"]
            )
    assert all(run["provider_calls"] == 1 for run in runs)
    assert all(run["retry_count"] == 0 for run in runs)
    assert all(run["final_schema_passed"] == "passed" for run in runs)
    assert all(run["stack_boundary_passed"] == "passed" for run in runs)
    assert all(run["duplicate_check_passed"] == "passed" for run in runs)
    assert execution.report["summary"]["pair_completion"] == {
        "expected": 15,
        "attempted": 15,
        "completed": 15,
        "incomplete": 0,
        "completion_basis": "both_variants_attempted",
    }

    question_packet = json.loads(
        execution.question_review_packet_path.read_text(encoding="utf-8")
    )
    metadata_packet = json.loads(
        execution.metadata_review_packet_path.read_text(encoding="utf-8")
    )
    assert len(question_packet["submissions"]) == 30
    assert len(metadata_packet["submissions"]) == 30
    assert all("variant" not in item for item in question_packet["submissions"])
    assert all("pair" not in item for item in metadata_packet["submissions"])
    assert all(len(item["questions"]) == 25 for item in question_packet["submissions"])

    finalized = runner.apply_blind_reviews(
        _complete_reviews(execution.review_template_path)
    )
    assert finalized.report["status"] == "completed"
    assert finalized.report["completion_status"] == "complete"
    assert finalized.report["quality"]["candidate"]["real_only"]["overall"] == 5
    assert finalized.report["quality"]["candidate"]["user_visible"]["overall"] == 5
    assert finalized.report["quality"]["candidate"]["user_visible"]["metadata_fit"] == 4
    assert finalized.report["summary"]["candidate_output_token_reduction"] == 0.6
    assert finalized.report["summary"]["token_comparison"]["relative"][
        "status"
    ] == "evaluated"
    assert finalized.report["summary"]["token_comparison"][
        "alternative_used"
    ] is False
    assert finalized.report["thresholds"]["verdict"] == "passed"

    report_text = finalized.report_json_path.read_text(encoding="utf-8")
    assert "RAW_PROVIDER_RESPONSE_MUST_NOT_BE_SAVED" not in report_text
    assert "resume_profile" not in report_text
    assert "Authorization" not in report_text
    assert "Bearer " not in report_text
    assert finalized.report["safety"] == {
        "full_upstream_chain_invoked": False,
        "background_tasks_created": False,
        "api_key_logged": False,
        "full_sensitive_inputs_logged": False,
        "raw_provider_responses_logged": False,
        "save_full_llm_logs_required": False,
        "production_default_agent_changed": False,
    }


@pytest.mark.asyncio
async def test_full_phase_is_blocked_until_smoke_and_pilot_pass(tmp_path) -> None:
    runner = QuestionBankABRunner(
        llm_client=PairedFakeProvider(),
        config=_config(tmp_path),
    )

    with pytest.raises(QuestionBankABProtocolError, match="Pilot must pass"):
        await runner.run_full()
    with pytest.raises(QuestionBankABProtocolError, match="smoke must pass"):
        await runner.run_pilot()


@pytest.mark.asyncio
async def test_pilot_records_candidate_retry_schema_failure_and_visible_fallback(
    tmp_path,
) -> None:
    provider = InvalidCandidateDraftProvider()
    runner = QuestionBankABRunner(
        llm_client=provider,
        config=_config(tmp_path),
    )

    await runner.run_smoke()
    artifacts = await runner.run_pilot()
    candidate_runs = [
        run for run in artifacts.report["runs"] if run["variant"] == "candidate"
    ]

    assert artifacts.report["pilot"]["status"] == "failed"
    assert artifacts.report["status"] == "pilot_failed"
    assert artifacts.report["summary"]["run_count"] == 6
    assert artifacts.report["summary"]["pair_completion"]["completed"] == 3
    assert len(candidate_runs) == 3
    assert all(run["execution_mode"] == "fallback" for run in candidate_runs)
    assert all(run["provider_calls"] == 2 for run in candidate_runs)
    assert all(run["retry_count"] == 1 for run in candidate_runs)
    assert all(run["failure_types"] == {"schema": 2} for run in candidate_runs)
    assert all(
        run["assembler_passed"] == "not_evaluated" for run in candidate_runs
    )
    assert all(run["final_schema_passed"] == "passed" for run in candidate_runs)


@pytest.mark.asyncio
async def test_global_lock_rejects_a_second_acceptance_process(tmp_path) -> None:
    config = _config(tmp_path)
    config.lock_path.write_text(
        json.dumps({"pid": 1234, "phase": "full"}), encoding="utf-8"
    )
    runner = QuestionBankABRunner(
        llm_client=PairedFakeProvider(),
        config=config,
    )

    with pytest.raises(QuestionBankABLockError, match="Another QuestionBank A/B"):
        await runner.run_smoke()


@pytest.mark.asyncio
async def test_absolute_deadline_cancels_inflight_call_without_background_task(
    tmp_path,
) -> None:
    provider = SmokeThenHangingProvider()
    runner = QuestionBankABRunner(
        llm_client=provider,
        config=_config(tmp_path, execution_deadline_seconds=0.02),
    )
    await runner.run_smoke()
    before = {id(task) for task in asyncio.all_tasks() if not task.done()}

    artifacts = await runner.run_pilot()
    await asyncio.sleep(0)
    after = {id(task) for task in asyncio.all_tasks() if not task.done()}

    assert artifacts.report["status"] == "pilot_failed"
    assert artifacts.report["completion_status"] == "incomplete"
    assert artifacts.report["summary"]["run_count"] == 6
    assert artifacts.report["summary"]["pair_completion"]["completed"] == 3
    assert all(
        run["terminal_status"] == "deadline" for run in artifacts.report["runs"]
    )
    for run in artifacts.report["runs"]:
        assert run["final_schema_passed"] == "not_evaluated"
        assert run["assembler_passed"] == "not_evaluated"
        assert run["strict_count_passed"] == "not_evaluated"
        assert run["stack_boundary_passed"] == "not_evaluated"
        assert run["duplicate_check_passed"] == "not_evaluated"
    for variant in ("baseline", "candidate"):
        variant_summary = artifacts.report["summary"]["variants"][variant]
        assert variant_summary["cross_stack_run_count"] == 0
        assert variant_summary["duplicate_run_count"] == 0
        assert variant_summary["content_checks"]["stack_boundary"] == {
            "evaluated": 0,
            "pass": 0,
            "fail": 0,
            "not_evaluated": 3,
        }
    assert provider.cancelled is True
    assert after <= before
    assert not runner.lock_path.exists()


@pytest.mark.asyncio
async def test_baseline_deadline_still_runs_candidate_and_candidate_only_pilot_passes(
    tmp_path,
) -> None:
    provider = SelectiveHangingProvider("QuestionBank")
    runner = QuestionBankABRunner(
        llm_client=provider,
        config=_config(tmp_path, execution_deadline_seconds=0.01),
    )
    await runner.run_smoke()

    artifacts = await runner.run_pilot()

    assert artifacts.report["pilot"]["status"] == "passed"
    assert artifacts.report["pilot"]["candidate_real_count"] == 3
    assert artifacts.report["pilot"]["completed_pair_count"] == 3
    assert artifacts.report["summary"]["run_count"] == 6
    baseline = [
        run for run in artifacts.report["runs"] if run["variant"] == "baseline"
    ]
    candidate = [
        run for run in artifacts.report["runs"] if run["variant"] == "candidate"
    ]
    assert all(run["terminal_status"] == "deadline" for run in baseline)
    assert all(run["execution_mode"] == "real" for run in candidate)
    assert all(run["final_schema_passed"] == "passed" for run in candidate)
    assert provider.cancelled_count == 3
    assert sum(
        request.response_schema_name == "QuestionDraftBank"
        for request in provider.requests
    ) == 3
    comparison = artifacts.report["summary"]["token_comparison"]
    assert comparison["relative"]["status"] == "not_evaluable"
    assert comparison["alternative_used"] is True
    assert comparison["candidate_absolute"]["average_output_tokens"] == 40
    assert comparison["effective_gate"] == {
        "method": "candidate_absolute_average",
        "status": "pass",
    }


@pytest.mark.asyncio
async def test_candidate_deadline_completes_every_pilot_pair_and_rejects_full(
    tmp_path,
) -> None:
    provider = SelectiveHangingProvider("QuestionDraftBank")
    runner = QuestionBankABRunner(
        llm_client=provider,
        config=_config(tmp_path, execution_deadline_seconds=0.01),
    )
    await runner.run_smoke()

    artifacts = await runner.run_pilot()

    assert artifacts.report["pilot"]["status"] == "failed"
    assert artifacts.report["summary"]["run_count"] == 6
    assert artifacts.report["summary"]["pair_completion"]["completed"] == 3
    candidate = [
        run for run in artifacts.report["runs"] if run["variant"] == "candidate"
    ]
    assert len(candidate) == 3
    assert all(run["terminal_status"] == "deadline" for run in candidate)
    assert provider.cancelled_count == 3
    with pytest.raises(QuestionBankABProtocolError, match="Pilot must pass"):
        await runner.run_full()


@pytest.mark.asyncio
async def test_all_baselines_deadline_uses_candidate_absolute_token_alternative(
    tmp_path,
) -> None:
    provider = SelectiveHangingProvider("QuestionBank")
    runner = QuestionBankABRunner(
        llm_client=provider,
        config=_config(tmp_path, execution_deadline_seconds=0.01),
    )
    await runner.run_smoke()
    await runner.run_pilot()

    artifacts = await runner.run_full()

    assert artifacts.report["status"] == "execution_completed"
    assert artifacts.report["summary"]["run_count"] == 30
    comparison = artifacts.report["summary"]["token_comparison"]
    assert comparison["relative"]["status"] == "not_evaluable"
    assert comparison["relative"]["threshold_status"] == "not_evaluable"
    assert comparison["baseline_all_deadline_censored"] is True
    assert comparison["alternative_used"] is True
    assert comparison["candidate_absolute"]["eligible_run_count"] == 15
    assert comparison["candidate_absolute"]["average_output_tokens"] == 40
    assert artifacts.report["thresholds"]["checks"][
        "output_token_reduction_gte_40pct"
    ]["status"] == "not_evaluable"
    assert artifacts.report["thresholds"]["checks"][
        "candidate_average_output_tokens_lte_1800"
    ]["status"] == "pass"
    assert artifacts.report["thresholds"]["checks"][
        "output_token_efficiency_gate"
    ] == {
        "status": "pass",
        "method": "candidate_absolute_average",
        "alternative_used": True,
    }


@pytest.mark.asyncio
async def test_incomplete_case_coverage_makes_relative_tokens_not_evaluable(
    tmp_path,
) -> None:
    provider = GoBaselineHangingProvider()
    runner = QuestionBankABRunner(
        llm_client=provider,
        config=_config(tmp_path, execution_deadline_seconds=0.01),
    )
    await runner.run_smoke()
    await runner.run_pilot()

    artifacts = await runner.run_full()

    comparison = artifacts.report["summary"]["token_comparison"]
    assert comparison["relative"]["comparable_pair_count"] == 10
    assert comparison["relative"]["status"] == "not_evaluable"
    assert comparison["relative"]["threshold_status"] == "not_evaluable"
    assert len(comparison["relative"]["comparable_case_ids"]) == 2
    assert comparison["baseline_all_deadline_censored"] is False
    assert comparison["alternative_used"] is False
    assert comparison["effective_gate"] == {
        "method": "none",
        "status": "not_evaluable",
    }
    assert artifacts.report["thresholds"]["checks"][
        "output_token_efficiency_gate"
    ]["status"] == "not_evaluable"


@pytest.mark.asyncio
async def test_absolute_token_alternative_fails_above_1800(tmp_path) -> None:
    provider = BaselineHangingHighTokenCandidateProvider()
    runner = QuestionBankABRunner(
        llm_client=provider,
        config=_config(tmp_path, execution_deadline_seconds=0.01),
    )
    await runner.run_smoke()
    await runner.run_pilot()

    artifacts = await runner.run_full()

    comparison = artifacts.report["summary"]["token_comparison"]
    assert comparison["alternative_used"] is True
    assert comparison["candidate_absolute"]["average_output_tokens"] == 1_801
    assert comparison["candidate_absolute"]["threshold_status"] == "fail"
    assert comparison["effective_gate"] == {
        "method": "candidate_absolute_average",
        "status": "fail",
    }
    assert artifacts.report["thresholds"]["checks"][
        "output_token_efficiency_gate"
    ]["status"] == "fail"


@pytest.mark.asyncio
async def test_provider_call_budget_stops_and_writes_incomplete_report(tmp_path) -> None:
    provider = PairedFakeProvider()
    runner = QuestionBankABRunner(
        llm_client=provider,
        config=_config(tmp_path, max_provider_calls=3),
    )

    await runner.run_smoke()
    artifacts = await runner.run_pilot()

    assert artifacts.report["status"] == "incomplete_budget"
    assert artifacts.report["completion_status"] == "incomplete"
    assert artifacts.report["stop_reason"] == "insufficient_budget_for_full_attempts"
    assert artifacts.report["budget"]["provider_calls_used"] == 2
    assert artifacts.report["summary"]["run_count"] == 1


@pytest.mark.asyncio
async def test_token_budget_stops_immediately_after_crossing_limit(tmp_path) -> None:
    provider = PairedFakeProvider()
    runner = QuestionBankABRunner(
        llm_client=provider,
        config=_config(tmp_path, max_total_tokens=50),
    )

    await runner.run_smoke()
    artifacts = await runner.run_pilot()

    assert artifacts.report["status"] == "incomplete_budget"
    assert artifacts.report["stop_reason"] == "total_token_budget_exceeded"
    assert artifacts.report["budget"]["total_tokens_used"] == 137
    assert artifacts.report["summary"]["run_count"] == 1


@pytest.mark.asyncio
async def test_asset_hash_change_invalidates_experiment_before_next_call(
    tmp_path,
) -> None:
    copied_asset = tmp_path / "frozen-agent.py"
    copied_asset.write_bytes(DEFAULT_ASSET_PATHS["baseline_agent"].read_bytes())
    provider = PairedFakeProvider()
    runner = QuestionBankABRunner(
        llm_client=provider,
        config=_config(tmp_path),
        asset_paths={"baseline_agent": copied_asset},
    )
    await runner.run_smoke()
    copied_asset.write_text("changed during experiment", encoding="utf-8")

    artifacts = await runner.run_pilot()

    assert artifacts.report["status"] == "invalidated_assets"
    assert artifacts.report["completion_status"] == "incomplete"
    assert artifacts.report["summary"]["run_count"] == 0
    assert len(provider.requests) == 1


@pytest.mark.asyncio
async def test_safety_constraint_failure_stops_before_any_ab_execution(
    tmp_path,
) -> None:
    provider = PairedFakeProvider()
    runner = QuestionBankABRunner(
        llm_client=provider,
        config=_config(tmp_path),
    )
    await runner.run_smoke()
    manifest = json.loads(runner.manifest_path.read_text(encoding="utf-8"))
    manifest["safety"]["raw_provider_responses_logged"] = True
    runner.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    artifacts = await runner.run_pilot()

    assert artifacts.report["status"] == "invalidated_safety"
    assert artifacts.report["completion_status"] == "incomplete"
    assert artifacts.report["stop_reason"] == "safety_constraint_failed"
    assert artifacts.report["summary"]["run_count"] == 0
    assert len(provider.requests) == 1
    assert not runner.lock_path.exists()


@pytest.mark.asyncio
async def test_damaged_manifest_stops_without_provider_call_and_releases_lock(
    tmp_path,
) -> None:
    provider = PairedFakeProvider()
    runner = QuestionBankABRunner(
        llm_client=provider,
        config=_config(tmp_path),
    )
    runner.config.run_dir.mkdir(parents=True)
    runner.manifest_path.write_text("{damaged", encoding="utf-8")

    with pytest.raises(QuestionBankABProtocolError, match="manifest"):
        await runner.run_smoke()

    assert provider.requests == []
    assert not runner.lock_path.exists()


def test_frozen_inputs_are_structured_and_exclude_raw_sensitive_fields() -> None:
    payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    serialized = json.dumps(payload, ensure_ascii=False).casefold()

    assert len(payload["cases"]) == 3
    assert {case["case_id"] for case in payload["cases"]} == {
        "backend_go_case",
        "backend_java_case",
        "backend_python_case",
    }
    assert "resume_text" not in serialized
    assert "jd_text" not in serialized
    assert "raw_text" not in serialized
    assert "api_key" not in serialized
