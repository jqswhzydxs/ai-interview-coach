import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from app.agents.llm_client import LLMRequest, LLMResponse, TokenUsage
from app.agents.question_draft_prompt_experiment import (
    PROMPT_ASSETS, QuestionDraftPromptAsset,
)
from app.services.question_draft_token_experiment import (
    HISTORICAL_REPORT_DIRS,
    QuestionDraftTokenExperimentConfig,
    QuestionDraftTokenExperimentProtocolError,
    QuestionDraftTokenExperimentRunner,
)
from tests.unit.test_question_bank_draft_protocol import _valid_draft


INPUT = Path("tests/fixtures/question_bank_ab_inputs_v1.json")


class PromptPairedProvider:
    provider = "offline-fake"
    model_name = "frozen-fake-model"

    def __init__(self, *, missing_usage=False, invalid=False, cross_stack=False):
        self.requests: list[LLMRequest] = []
        self.missing_usage = missing_usage
        self.invalid = invalid
        self.cross_stack = cross_stack

    def variant(self, request):
        for variant, asset in PROMPT_ASSETS.items():
            if asset.path.read_text(encoding="utf-8") in request.system_prompt:
                return variant
        raise AssertionError("unknown prompt")

    async def generate_json(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        variant = self.variant(request)
        input_data = json.loads(request.user_prompt)
        technology = input_data["resume_profile"]["skills"][0]
        content = {"invalid": True} if self.invalid else _valid_draft(technology)
        if self.cross_stack and not self.invalid:
            content["professional_questions"][0]["question_text"] = "How should Ruby on Rails own this API boundary?"
        output_tokens = 2_000 if variant == "baseline" else 1_600
        usage = None if self.missing_usage else TokenUsage(
            input_tokens=400, output_tokens=output_tokens,
            total_tokens=400 + output_tokens,
        )
        return LLMResponse(
            provider=self.provider, model_name=self.model_name,
            content=content, usage=usage,
            raw_text="RAW_RESPONSE_MUST_NOT_BE_PERSISTED",
        )


class HangingBaselineProvider(PromptPairedProvider):
    def __init__(self):
        super().__init__()
        self.cancelled = 0

    async def generate_json(self, request):
        if self.variant(request) == "baseline":
            self.requests.append(request)
            try:
                await asyncio.Event().wait()
            finally:
                self.cancelled += 1
        return await super().generate_json(request)


def config(tmp_path, **overrides):
    values = {
        "input_path": INPUT,
        "run_dir": tmp_path / "run",
        "lock_path": tmp_path / ".phase-2.4d.lock",
        "execution_deadline_seconds": 0.05,
    }
    values.update(overrides)
    return QuestionDraftTokenExperimentConfig(**values)


async def completed_runner(tmp_path):
    provider = PromptPairedProvider()
    runner = QuestionDraftTokenExperimentRunner(llm_client=provider, config=config(tmp_path))
    assert runner.prepare().report["budget"]["provider_calls_used"] == 0
    assert (await runner.run_smoke()).report["status"] == "smoke_passed"
    assert (await runner.run_pilot()).report["status"] == "pilot_passed"
    pilot_calls = len(provider.requests)
    assert (await runner.run_pilot()).report["status"] == "pilot_passed"
    assert len(provider.requests) == pilot_calls
    artifacts = await runner.run_full()
    return provider, runner, artifacts


@pytest.mark.asyncio
async def test_full_protocol_is_paired_prompt_only_and_idempotent(tmp_path):
    provider, runner, artifacts = await completed_runner(tmp_path)
    report = artifacts.report
    assert report["status"] == "execution_completed"
    assert report["summary"]["run_count"] == 30
    assert len(provider.requests) == 31  # candidate smoke + 30 paired executions
    assert {request.response_schema_name for request in provider.requests} == {"QuestionDraftBank"}
    assert report["budget"]["provider_calls_used"] == 31
    assert report["summary"]["token_comparison"] == {
        "status": "evaluated",
        "comparable_pair_count": 15,
        "minimum_comparable_pair_count": 12,
        "baseline_output_tokens": 30_000,
        "candidate_output_tokens": 24_000,
        "candidate_average_output_tokens": 1_600.0,
        "paired_output_token_reduction": 0.2,
        "character_length_is_token_substitute": False,
    }
    gates = report["thresholds"]["gates"]
    assert gates["candidate_average_output_tokens_lte_1800"]["status"] == "pass"
    assert gates["paired_output_token_reduction_gte_10pct"]["status"] == "pass"
    assert report["thresholds"]["verdict"] == "pending"
    runs = report["runs"]
    assert [(r["pair"], r["variant"]) for r in runs[:6]] == [
        (1, "baseline"), (1, "candidate"),
        (1, "baseline"), (1, "candidate"),
        (1, "baseline"), (1, "candidate"),
    ]
    pair_two = [r["variant"] for r in runs if r["pair"] == 2]
    assert pair_two == ["candidate", "baseline"] * 3
    assert all(r["metadata_assembler_version"] == "deterministic-metadata-v2" for r in runs)
    assert all(r["metadata_v2_applied"] for r in runs)
    assert all(r["max_tokens"] is None and r["temperature"] == 0.2 for r in runs)
    assert all(r["length_diagnostics"]["overall"]["count"] == 25 for r in runs)
    candidate_lengths = report["summary"]["variants"]["candidate"]["length_diagnostics"]
    assert candidate_lengths["question_count"] == 375
    assert set(candidate_lengths["overall"]) == {"count", "average", "p50", "p95", "max"}
    assert {r["prompt_version"] for r in runs} == {
        "question_bank_draft_agent_v0.1", "question_bank_draft_agent_v0.2"
    }
    assert {r["prompt_sha256"] for r in runs} == {
        PROMPT_ASSETS["baseline"].sha256, PROMPT_ASSETS["candidate"].sha256
    }
    audit = json.loads(runner.audit_path.read_text(encoding="utf-8"))
    assert all(r["input"] and r["output"] for r in audit["runs"])
    assert "RAW_RESPONSE_MUST_NOT_BE_PERSISTED" not in runner.audit_path.read_text(encoding="utf-8")
    calls_before = len(provider.requests)
    hashes_before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in runner.config.run_dir.rglob("*") if p.is_file()}
    second = await runner.run_full()
    hashes_after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in runner.config.run_dir.rglob("*") if p.is_file()}
    assert len(provider.requests) == calls_before
    assert second.report == report
    assert hashes_after == hashes_before


@pytest.mark.asyncio
async def test_blind_packet_hides_variant_and_review_gates_finalize(tmp_path):
    _, runner, artifacts = await completed_runner(tmp_path)
    packet = json.loads(artifacts.blind_packet_path.read_text(encoding="utf-8"))
    template = json.loads(artifacts.review_template_path.read_text(encoding="utf-8"))
    assert len(packet["submissions"]) == len(template["submissions"]) == 30
    banned = {"variant", "prompt_version", "prompt_sha256", "case_id", "pair", "execution_order", "output_fingerprint"}

    def inspect(value):
        if isinstance(value, dict):
            assert not (set(value) & banned)
            for item in value.values():
                inspect(item)
        elif isinstance(value, list):
            for item in value:
                inspect(item)

    inspect(packet)
    assert all(row["text_scores"] == {key: None for key in row["text_scores"]} for row in template["submissions"])
    template["evaluator"] = {
        "type": "AI", "identifier": "independent-offline-test-evaluator",
        "independence_confirmed": True,
    }
    for row in template["submissions"]:
        row["text_scores"] = {key: 4 for key in row["text_scores"]}
        row["metadata_fit_scores"] = [4] * 25
    review = tmp_path / "completed-review.json"
    review.write_text(json.dumps(template), encoding="utf-8")
    final = runner.apply_blind_review(review).report
    assert final["review"]["evaluator"]["type"] == "AI"
    assert final["thresholds"]["verdict"] == "pass"
    assert final["summary"]["quality"]["candidate"]["text_quality_mean"] == 4
    assert final["summary"]["quality"]["candidate"]["metadata_fit_mean"] == 4


@pytest.mark.asyncio
async def test_pilot_has_only_three_comparable_pairs_and_token_gate_not_evaluable(tmp_path):
    provider = PromptPairedProvider()
    runner = QuestionDraftTokenExperimentRunner(llm_client=provider, config=config(tmp_path))
    await runner.run_smoke()
    report = (await runner.run_pilot()).report
    comparison = report["summary"]["token_comparison"]
    assert report["summary"]["run_count"] == 6
    assert comparison["comparable_pair_count"] == 3
    assert comparison["status"] == "not_evaluable"
    assert comparison["candidate_average_output_tokens"] is None
    assert report["thresholds"]["gates"]["candidate_average_output_tokens_lte_1800"]["status"] == "not_evaluable"


@pytest.mark.asyncio
async def test_deadline_terminates_one_variant_but_attempts_pair_mate(tmp_path):
    provider = HangingBaselineProvider()
    runner = QuestionDraftTokenExperimentRunner(llm_client=provider, config=config(tmp_path))
    assert (await runner.run_smoke()).report["status"] == "smoke_passed"
    report = (await runner.run_pilot()).report
    assert provider.cancelled == 1
    assert len(report["runs"]) == 2
    baseline, candidate = report["runs"]
    assert baseline["variant"] == "baseline" and baseline["terminal_status"] == "deadline"
    assert candidate["variant"] == "candidate" and candidate["execution_mode"] == "real"
    assert report["budget"]["unknown_usage_calls"] == 1


@pytest.mark.asyncio
async def test_missing_usage_is_unknown_never_zero(tmp_path):
    runner = QuestionDraftTokenExperimentRunner(
        llm_client=PromptPairedProvider(missing_usage=True), config=config(tmp_path)
    )
    report = (await runner.run_smoke()).report
    smoke = report["smoke"]
    assert report["status"] == "smoke_failed"
    assert report["stop_reason"] == "smoke_usage_unknown"
    assert smoke["token_usage_status"] == "unknown"
    assert smoke["usage_complete"] is False
    assert smoke["input_tokens"] is smoke["output_tokens"] is smoke["total_tokens"] is None
    assert report["budget"]["total_tokens_used"] is None
    assert report["summary"]["token_comparison"]["status"] == "not_evaluable"


@pytest.mark.asyncio
async def test_retry_fallback_and_budgets_are_recorded(tmp_path):
    provider = PromptPairedProvider(invalid=True)
    runner = QuestionDraftTokenExperimentRunner(
        llm_client=provider, config=config(tmp_path, max_provider_calls=2)
    )
    report = (await runner.run_smoke()).report
    assert report["status"] == "smoke_failed"
    assert report["smoke"]["execution_mode"] == "fallback"
    assert report["smoke"]["provider_calls"] == 2
    assert report["smoke"]["retry_count"] == 1
    assert report["budget"]["provider_calls_used"] == 2
    assert report["smoke"]["failure_types"] == {"schema": 2}


@pytest.mark.asyncio
async def test_assembler_failure_falls_back_without_variant_mix(tmp_path):
    provider = PromptPairedProvider(cross_stack=True)
    runner = QuestionDraftTokenExperimentRunner(llm_client=provider, config=config(tmp_path))
    report = (await runner.run_smoke()).report
    assert report["smoke"]["execution_mode"] == "fallback"
    assert report["smoke"]["assembler_passed"] == "failed"
    assert report["smoke"]["metadata_v2_applied"] is False
    assert report["smoke"]["metadata_assembler_version"] == "deterministic-metadata-v2"


@pytest.mark.asyncio
async def test_known_token_budget_fails_closed_at_smoke(tmp_path):
    runner = QuestionDraftTokenExperimentRunner(
        llm_client=PromptPairedProvider(), config=config(tmp_path, max_total_tokens=1_000)
    )
    report = (await runner.run_smoke()).report
    assert report["status"] == "smoke_failed"
    assert report["stop_reason"] == "smoke_token_budget_exceeded"
    assert report["budget"]["known_total_tokens"] == 2_000


def test_prepare_is_offline_idempotent_and_historical_dirs_are_rejected(tmp_path):
    provider = PromptPairedProvider()
    runner = QuestionDraftTokenExperimentRunner(llm_client=provider, config=config(tmp_path))
    first = runner.prepare().report
    second = runner.prepare().report
    assert first == second
    assert provider.requests == []
    for path in HISTORICAL_REPORT_DIRS:
        with pytest.raises(QuestionDraftTokenExperimentProtocolError, match="historical"):
            QuestionDraftTokenExperimentRunner(
                llm_client=provider,
                config=QuestionDraftTokenExperimentConfig(input_path=INPUT, run_dir=path),
            )


def test_runner_detects_prompt_hash_drift_without_provider_call(tmp_path, monkeypatch):
    provider = PromptPairedProvider()
    runner = QuestionDraftTokenExperimentRunner(llm_client=provider, config=config(tmp_path))
    changed = tmp_path / "changed-prompt.md"
    changed.write_text("changed only for drift test", encoding="utf-8")
    monkeypatch.setitem(
        PROMPT_ASSETS,
        "candidate",
        QuestionDraftPromptAsset(
            variant="candidate",
            prompt_version="question_bank_draft_agent_v0.2",
            relative_path=changed.as_posix(),
        ),
    )
    # Absolute paths are valid Path joins and intentionally produce a different hash.
    with pytest.raises(QuestionDraftTokenExperimentProtocolError, match="Prompt hash drift"):
        runner.prepare()
    assert provider.requests == []


def test_non_frozen_input_fixture_is_rejected(tmp_path):
    changed = tmp_path / "changed-input.json"
    payload = json.loads(INPUT.read_text(encoding="utf-8"))
    payload["cases"][0]["input"]["preparation_goal"] = "changed"
    changed.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(QuestionDraftTokenExperimentProtocolError, match="frozen input hash"):
        QuestionDraftTokenExperimentRunner(
            llm_client=PromptPairedProvider(),
            config=QuestionDraftTokenExperimentConfig(
                input_path=changed, run_dir=tmp_path / "changed-run"
            ),
        )
