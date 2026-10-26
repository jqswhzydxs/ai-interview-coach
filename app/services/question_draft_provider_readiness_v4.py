"""Single-call Provider readiness executor for Phase 2.4D-E-A.

The executor never calls ``BaseAgent.execute``.  It builds the frozen candidate
request and invokes the injected Provider client exactly once per readiness
attempt, so Agent retry and fallback are structurally unavailable.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any

from app.agents.deepseek_reasoning_effort_experiment_client import safe_usage_details_record
from app.agents.llm_client import LLMClient
from app.agents.question_bank_candidate_agent import payload_sha256
from app.agents.question_bank_metadata_v2 import QuestionBankMetadataAssemblerV2
from app.agents.question_draft_prompt_experiment import (
    PROMPT_ASSETS,
    QuestionDraftPromptExperimentAgent,
)
from app.schemas.question import QuestionBank
from app.schemas.question_draft import QuestionDraftBank
from app.services.provider_failure_observability import (
    provider_failure_fields,
    safe_token_usage,
    usage_status,
)
from app.services.question_bank_ab_service import (
    CHECK_FAILED,
    CHECK_NOT_EVALUATED,
    CHECK_PASSED,
    _analyze_bank,
    _load_frozen_cases,
)
from app.services.question_bank_metadata_replay import validate_evidence_quotes
from app.services.question_draft_token_experiment import FROZEN_INPUT_SHA256
from app.services.question_draft_reasoning_effort_protocol_v4 import (
    PROTOCOL_VERSION,
    ProviderReadinessGateV4,
    QuestionDraftReasoningProtocolV4Error,
    account_execution_v4,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_PROVIDER = "deepseek"
REQUIRED_MODEL = "deepseek-v4-pro"
GO_CASE_ID = "backend_go_case"
READINESS_DEADLINE_SECONDS = 120.0
READINESS_PROMPT_VARIANT = "candidate"
READINESS_REASONING_EFFORT = "low"
READINESS_LEDGER_VERSION = PROTOCOL_VERSION + "-provider-readiness-v1"
DEFAULT_FIXTURE_PATH = PROJECT_ROOT / "tests/fixtures/question_bank_ab_inputs_v1.json"
READINESS_ASSETS = {
    "candidate_prompt": PROMPT_ASSETS[READINESS_PROMPT_VARIANT].path,
    "draft_schema": PROJECT_ROOT / "app/schemas/question_draft.py",
    "final_schema": PROJECT_ROOT / "app/schemas/question.py",
    "frozen_fixture": DEFAULT_FIXTURE_PATH,
    "metadata_v2_assembler": PROJECT_ROOT / "app/agents/question_bank_metadata_v2.py",
    "metadata_rules": PROJECT_ROOT / "app/agents/question_metadata_rules.py",
    "assembler_checks": PROJECT_ROOT / "app/agents/question_bank_assembler.py",
    "experiment_agent": PROJECT_ROOT / "app/agents/question_draft_prompt_experiment.py",
    "experiment_provider_client": PROJECT_ROOT
    / "app/agents/deepseek_reasoning_effort_experiment_client.py",
    "usage_detail_parser": PROJECT_ROOT / "app/services/provider_usage_details.py",
    "reasoning_effort_protocol": PROJECT_ROOT
    / "app/services/question_draft_reasoning_effort_protocol_v4.py",
    "readiness_runner": Path(__file__).resolve(),
}


class QuestionDraftProviderReadinessV4Error(RuntimeError):
    pass


@dataclass(frozen=True)
class QuestionDraftProviderReadinessV4Config:
    ledger_path: Path
    fixture_path: Path = DEFAULT_FIXTURE_PATH
    deadline_seconds: float = READINESS_DEADLINE_SECONDS
    lock_path: Path | None = None

    def __post_init__(self) -> None:
        if self.deadline_seconds != READINESS_DEADLINE_SECONDS:
            raise ValueError("Readiness deadline is frozen at 120 seconds")


@dataclass(frozen=True)
class QuestionDraftProviderReadinessV4Artifacts:
    ledger_path: Path
    ledger: dict[str, Any]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def readiness_asset_snapshot(fixture_path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    if fixture_path.resolve() != DEFAULT_FIXTURE_PATH.resolve():
        raise QuestionDraftProviderReadinessV4Error(
            "Readiness requires the frozen Phase 2.4D fixture path"
        )
    if _sha256(fixture_path) != FROZEN_INPUT_SHA256:
        raise QuestionDraftProviderReadinessV4Error("Frozen fixture hash drift detected")
    assets = dict(READINESS_ASSETS)
    assets["frozen_fixture"] = fixture_path
    hashes = {
        name: {
            "path": path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(),
            "sha256": _sha256(path),
        }
        for name, path in sorted(assets.items())
    }
    return {
        "prompt": {
            "version": PROMPT_ASSETS[READINESS_PROMPT_VARIANT].prompt_version,
            **hashes["candidate_prompt"],
        },
        "schemas": {
            "question_draft": hashes["draft_schema"],
            "question_bank": hashes["final_schema"],
        },
        "fixture": {
            "case_id": GO_CASE_ID,
            **hashes["frozen_fixture"],
        },
        "metadata_v2": {
            "version": QuestionBankMetadataAssemblerV2.version,
            "assembler": hashes["metadata_v2_assembler"],
            "rules": hashes["metadata_rules"],
            "checks": hashes["assembler_checks"],
        },
        "request_builder": hashes["experiment_agent"],
        "experiment_provider_client": hashes["experiment_provider_client"],
        "usage_detail_parser": hashes["usage_detail_parser"],
        "reasoning_effort_protocol": hashes["reasoning_effort_protocol"],
        "readiness_runner": hashes["readiness_runner"],
    }


def readiness_asset_bundle_sha256(
    fixture_path: Path = DEFAULT_FIXTURE_PATH,
) -> str:
    canonical = json.dumps(
        readiness_asset_snapshot(fixture_path),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def readiness_ledger_sha256(path: Path) -> str:
    return _sha256(path)


def _content_checks_template() -> dict[str, str]:
    return {
        "draft_schema": CHECK_NOT_EVALUATED,
        "metadata_v2_assembler": CHECK_NOT_EVALUATED,
        "final_schema": CHECK_NOT_EVALUATED,
        "strict_count": CHECK_NOT_EVALUATED,
        "stack_boundary": CHECK_NOT_EVALUATED,
        "duplicate": CHECK_NOT_EVALUATED,
        "evidence_safety": CHECK_NOT_EVALUATED,
    }


def readiness_protocol_snapshot() -> dict[str, Any]:
    return {
        "fixture_case_id": GO_CASE_ID,
        "prompt_variant": READINESS_PROMPT_VARIANT,
        "request_schema": "QuestionDraftBank",
        "metadata_assembler": QuestionBankMetadataAssemblerV2.version,
        "temperature": 0.2,
        "max_tokens": None,
        "thinking": {"type": "enabled"},
        "reasoning_effort": READINESS_REASONING_EFFORT,
        "reasoning_effort_explicit": True,
        "client_timeout_seconds": 60,
        "deadline_seconds": READINESS_DEADLINE_SECONDS,
        "agent_retry": 0,
        "fallback": False,
        "outputs_count_toward_ab": False,
    }


def validate_readiness_content(
    content: dict[str, Any], input_data: dict[str, Any]
) -> tuple[QuestionBank | None, dict[str, str], str | None]:
    """Validate a Provider payload without returning or persisting its text."""

    checks = _content_checks_template()
    try:
        draft = QuestionDraftBank.model_validate(content)
        checks["draft_schema"] = CHECK_PASSED
    except Exception:
        checks["draft_schema"] = CHECK_FAILED
        return None, checks, "draft_schema"
    try:
        assembled = QuestionBankMetadataAssemblerV2().assemble(draft, input_data)
        checks["metadata_v2_assembler"] = CHECK_PASSED
    except Exception:
        checks["metadata_v2_assembler"] = CHECK_FAILED
        return None, checks, "metadata_v2_assembler"
    try:
        bank = QuestionBank.model_validate(assembled)
        checks["final_schema"] = CHECK_PASSED
    except Exception:
        checks["final_schema"] = CHECK_FAILED
        return None, checks, "final_schema"

    analysis = _analyze_bank(bank, input_data)
    checks["strict_count"] = (
        CHECK_PASSED if analysis["strict_count_passed"] else CHECK_FAILED
    )
    checks["stack_boundary"] = (
        CHECK_PASSED if analysis["stack_boundary_passed"] else CHECK_FAILED
    )
    checks["duplicate"] = (
        CHECK_PASSED if analysis["duplicate_check_passed"] else CHECK_FAILED
    )
    try:
        validate_evidence_quotes(bank.model_dump(mode="json"), input_data)
        checks["evidence_safety"] = CHECK_PASSED
    except Exception:
        checks["evidence_safety"] = CHECK_FAILED
    failed_stage = next(
        (name for name, status in checks.items() if status != CHECK_PASSED), None
    )
    return bank, checks, failed_stage


def content_checks_passed(checks: dict[str, str]) -> bool:
    return bool(checks) and all(status == CHECK_PASSED for status in checks.values())


def load_and_validate_readiness_ledger(
    ledger_path: Path,
    *,
    provider: str,
    model: str,
    fixture_path: Path = DEFAULT_FIXTURE_PATH,
    require_passed: bool,
) -> dict[str, Any]:
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QuestionDraftProviderReadinessV4Error(
            "Readiness ledger is missing or unreadable"
        ) from exc
    if not isinstance(ledger, dict):
        raise QuestionDraftProviderReadinessV4Error("Readiness ledger must be an object")
    expected_assets = readiness_asset_snapshot(fixture_path)
    expected_bundle = readiness_asset_bundle_sha256(fixture_path)
    expected = {
        "protocol_version": PROTOCOL_VERSION,
        "ledger_version": READINESS_LEDGER_VERSION,
        "record_type": "provider_readiness_gate",
        "scope": "readiness_only_not_token_ab",
        "provider": provider,
        "model": model,
        "frozen_assets_sha256": expected_bundle,
        "asset_bundle_sha256": expected_bundle,
        "assets": expected_assets,
        "protocol": readiness_protocol_snapshot(),
        "max_attempts": 2,
        "provider_calls_per_attempt": 1,
    }
    for key, value in expected.items():
        if ledger.get(key) != value:
            raise QuestionDraftProviderReadinessV4Error(
                f"Readiness ledger {key} drift detected"
            )
    if ledger.get("active_attempt") is not None:
        raise QuestionDraftProviderReadinessV4Error(
            "Readiness ledger contains an interrupted attempt; automatic retry is forbidden"
        )
    attempts = ledger.get("attempts")
    if not isinstance(attempts, list) or len(attempts) > 2:
        raise QuestionDraftProviderReadinessV4Error("Invalid readiness attempt history")
    if require_passed:
        if ledger.get("status") != "passed":
            raise QuestionDraftProviderReadinessV4Error(
                "Provider readiness has not passed"
            )
        passed = [attempt for attempt in attempts if attempt.get("passed") is True]
        if len(passed) != 1:
            raise QuestionDraftProviderReadinessV4Error(
                "Readiness ledger must contain exactly one passing attempt"
            )
        final = passed[0]
        accounting = final.get("accounting")
        checks = final.get("content_checks")
        if not isinstance(accounting, dict) or not isinstance(checks, dict):
            raise QuestionDraftProviderReadinessV4Error(
                "Passing readiness attempt is incomplete"
            )
        if (
            accounting.get("successful_response_usage", {}).get("status") != "complete"
            or accounting.get("billing_usage_completeness", {}).get("status")
            != "complete"
            or not content_checks_passed(checks)
        ):
            raise QuestionDraftProviderReadinessV4Error(
                "Passing readiness attempt does not satisfy protocol v4"
            )
    return ledger


class QuestionDraftProviderReadinessV4Runner:
    def __init__(
        self,
        *,
        llm_client: LLMClient,
        config: QuestionDraftProviderReadinessV4Config,
    ) -> None:
        self.llm_client = llm_client
        self.config = config
        if (
            llm_client.provider != REQUIRED_PROVIDER
            or llm_client.model_name != REQUIRED_MODEL
        ):
            raise QuestionDraftProviderReadinessV4Error(
                "Protocol v4 readiness requires deepseek/deepseek-v4-pro"
            )
        if getattr(llm_client, "thinking_type", None) != "enabled":
            raise QuestionDraftProviderReadinessV4Error(
                "Protocol v4 readiness requires thinking.type=enabled"
            )
        if getattr(llm_client, "reasoning_effort", None) != READINESS_REASONING_EFFORT:
            raise QuestionDraftProviderReadinessV4Error(
                "Protocol v4 readiness requires explicit reasoning_effort=low"
            )
        self.ledger_path = config.ledger_path
        self.lock_path = config.lock_path or config.ledger_path.with_suffix(".lock")

    def prepare(self) -> QuestionDraftProviderReadinessV4Artifacts:
        """Create or validate the single readiness ledger without a Provider call."""

        with self._exclusive_lock():
            assets = readiness_asset_snapshot(self.config.fixture_path)
            bundle = readiness_asset_bundle_sha256(self.config.fixture_path)
            if self.ledger_path.exists():
                ledger = load_and_validate_readiness_ledger(
                    self.ledger_path,
                    provider=self.llm_client.provider,
                    model=self.llm_client.model_name,
                    fixture_path=self.config.fixture_path,
                    require_passed=False,
                )
                return self._artifacts(ledger)
            gate = ProviderReadinessGateV4(
                ledger_path=self.ledger_path,
                provider=self.llm_client.provider,
                model=self.llm_client.model_name,
                frozen_assets_sha256=bundle,
            )
            ledger = gate.state
            ledger.update(
                {
                    "ledger_version": READINESS_LEDGER_VERSION,
                    "asset_bundle_sha256": bundle,
                    "assets": assets,
                    "protocol": readiness_protocol_snapshot(),
                    "active_attempt": None,
                }
            )
            _atomic_json(self.ledger_path, ledger)
            return self._artifacts(ledger)

    def status(self) -> QuestionDraftProviderReadinessV4Artifacts:
        ledger = load_and_validate_readiness_ledger(
            self.ledger_path,
            provider=self.llm_client.provider,
            model=self.llm_client.model_name,
            fixture_path=self.config.fixture_path,
            require_passed=False,
        )
        return self._artifacts(ledger)

    async def attempt(self) -> QuestionDraftProviderReadinessV4Artifacts:
        """Run at most one Provider call; terminal ledgers are returned unchanged."""

        with self._exclusive_lock():
            ledger = load_and_validate_readiness_ledger(
                self.ledger_path,
                provider=self.llm_client.provider,
                model=self.llm_client.model_name,
                fixture_path=self.config.fixture_path,
                require_passed=False,
            )
            if ledger["status"] in {"passed", "blocked"}:
                return self._artifacts(ledger)
            attempt_number = len(ledger["attempts"]) + 1
            started_at = self._iso_now()
            case = self._go_case()
            request, prompt_sha256, provider_request_sha256 = self._request(
                case["input"]
            )
            ledger["active_attempt"] = {
                "attempt": attempt_number,
                "started_at": started_at,
                "status": "started",
            }
            _atomic_json(self.ledger_path, ledger)
            provider_call: dict[str, Any] = {
                "call": 1,
                "started_at": started_at,
            }
            content_checks = _content_checks_template()
            bank: QuestionBank | None = None
            failed_stage: str | None = None
            response_received = False
            started = perf_counter()
            try:
                async with asyncio.timeout(self.config.deadline_seconds):
                    response = await self.llm_client.generate_json(request)
                response_received = True
                usage = safe_token_usage(response.usage)
                provider_call.update(
                    {
                        "status": "succeeded",
                        "latency_ms": _elapsed_ms(started),
                        "token_usage": usage,
                        "token_usage_status": usage_status(usage),
                        "usage_details": safe_usage_details_record(response),
                        "failure_category": None,
                        "exception_type": None,
                        "http_status_code": None,
                        "provider_error_code": None,
                        "request_id": None,
                        "retry_after": None,
                        "filtered_fields": [],
                    }
                )
                if (
                    response.provider != self.llm_client.provider
                    or response.model_name != self.llm_client.model_name
                ):
                    failed_stage = "provider_identity"
                else:
                    bank, content_checks, failed_stage = validate_readiness_content(
                        response.content, case["input"]
                    )
            except (Exception, asyncio.CancelledError) as exc:
                usage = safe_token_usage(getattr(exc, "usage", None))
                provider_call.update(
                    {
                        "status": "failed",
                        "latency_ms": _elapsed_ms(started),
                        "token_usage": usage,
                        "token_usage_status": usage_status(usage),
                        "usage_details": safe_usage_details_record(None),
                        **provider_failure_fields(
                            exc,
                            sensitive_values=(request.system_prompt, request.user_prompt),
                        ),
                    }
                )

            safe_valid = response_received and content_checks_passed(content_checks)
            accounting = account_execution_v4(
                [provider_call],
                final_execution_mode="real" if response_received else None,
                final_output_safe_valid=safe_valid,
                provider_call_limit=1,
                terminal_status="completed" if response_received else "failed",
            )
            gate = ProviderReadinessGateV4(
                ledger_path=self.ledger_path,
                provider=self.llm_client.provider,
                model=self.llm_client.model_name,
                frozen_assets_sha256=readiness_asset_bundle_sha256(
                    self.config.fixture_path
                ),
            )
            gate.record_attempt(accounting)
            ledger = json.loads(self.ledger_path.read_text(encoding="utf-8"))
            result = ledger["attempts"][-1]
            result.update(
                {
                    "started_at": started_at,
                    "finished_at": self._iso_now(),
                    "start_status": "started",
                    "end_status": "passed" if result["passed"] else "failed",
                    "provider_call_count": 1,
                    "retry_count": 0,
                    "fallback_used": False,
                    "provider_call": provider_call,
                    "successful_response_usage": accounting[
                        "successful_response_usage"
                    ],
                    "billing_usage_completeness": accounting[
                        "billing_usage_completeness"
                    ],
                    "known_token_lower_bound": accounting[
                        "known_token_lower_bound"
                    ],
                    "execution_reliability": accounting[
                        "execution_reliability"
                    ],
                    "accounting": accounting,
                    "content_checks": content_checks,
                    "content_failure_stage": failed_stage,
                    "prompt_sha256": prompt_sha256,
                    "provider_request_sha256": provider_request_sha256,
                    "thinking": {"type": "enabled"},
                    "reasoning_effort": READINESS_REASONING_EFFORT,
                    "reasoning_effort_present": True,
                    "input_sha256": payload_sha256(case["input"]),
                    "output_fingerprint": (
                        payload_sha256(bank.model_dump(mode="json")) if bank else None
                    ),
                }
            )
            ledger["active_attempt"] = None
            _atomic_json(self.ledger_path, ledger)
            return self._artifacts(ledger)

    def _go_case(self) -> dict[str, Any]:
        cases = _load_frozen_cases(self.config.fixture_path)
        matches = [case for case in cases if case["case_id"] == GO_CASE_ID]
        if len(matches) != 1:
            raise QuestionDraftProviderReadinessV4Error(
                "Frozen Go readiness fixture is unavailable"
            )
        return matches[0]

    def _request(self, input_data: dict[str, Any]):
        asset = PROMPT_ASSETS[READINESS_PROMPT_VARIANT]
        agent = QuestionDraftPromptExperimentAgent(
            self.llm_client,
            prompt_variant=READINESS_PROMPT_VARIANT,
            expected_prompt_sha256=asset.sha256,
            max_real_llm_attempts=1,
            use_real_llm=True,
        )
        request = agent._build_request(input_data, QuestionDraftBank)
        prompt_text = asset.path.read_text(encoding="utf-8")
        if (
            agent.max_real_llm_attempts != 1
            or request.temperature != 0.2
            or request.response_schema_name != "QuestionDraftBank"
            or prompt_text not in request.system_prompt
        ):
            raise QuestionDraftProviderReadinessV4Error(
                "Frozen readiness request parameters drifted"
            )
        payload_builder = getattr(self.llm_client, "request_payload", None)
        if not callable(payload_builder):
            raise QuestionDraftProviderReadinessV4Error(
                "Protocol v4 readiness client must expose its exact request payload"
            )
        provider_request = payload_builder(request)
        if (
            not isinstance(provider_request, dict)
            or provider_request.get("thinking") != {"type": "enabled"}
            or provider_request.get("reasoning_effort")
            != READINESS_REASONING_EFFORT
            or provider_request.get("response_format")
            != {"type": "json_object"}
        ):
            raise QuestionDraftProviderReadinessV4Error(
                "Frozen readiness Provider request controls drifted"
            )
        return request, asset.sha256, payload_sha256(provider_request)

    def _artifacts(self, ledger: dict[str, Any]) -> QuestionDraftProviderReadinessV4Artifacts:
        return QuestionDraftProviderReadinessV4Artifacts(
            ledger_path=self.ledger_path,
            ledger=json.loads(json.dumps(ledger)),
        )

    @contextmanager
    def _exclusive_lock(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(
                self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY
            )
        except FileExistsError as exc:
            raise QuestionDraftProviderReadinessV4Error(
                "Another readiness process holds the ledger lock"
            ) from exc
        try:
            os.write(descriptor, str(os.getpid()).encode("ascii"))
            os.close(descriptor)
            yield
        finally:
            try:
                self.lock_path.unlink()
            except FileNotFoundError:
                pass

    @staticmethod
    def _iso_now() -> str:
        return datetime.now(timezone.utc).isoformat()


def _elapsed_ms(started: float) -> int:
    return max(0, int((perf_counter() - started) * 1000))


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def readiness_status_from_path(path: Path) -> dict[str, Any]:
    """Return a bounded status view without requiring Provider configuration."""

    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QuestionDraftProviderReadinessV4Error(
            "Readiness ledger is missing or unreadable"
        ) from exc
    return {
        "protocol_version": ledger.get("protocol_version"),
        "ledger_version": ledger.get("ledger_version"),
        "status": ledger.get("status"),
        "provider": ledger.get("provider"),
        "model": ledger.get("model"),
        "attempts_used": len(ledger.get("attempts", [])),
        "attempts_limit": ledger.get("max_attempts"),
        "ledger_sha256": readiness_ledger_sha256(path),
    }
