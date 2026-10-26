"""Offline-only Phase 2.4D-B incident and protocol review artifact builder."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

import httpx

from app.services.question_draft_token_protocol_v2 import (
    PROTOCOL_VERSION,
    account_execution_v2,
    protocol_v2_snapshot,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_NAMES = (
    "question-bank-token-phase-2-4d-b-20261022-run1",
    "question-bank-token-phase-2-4d-b-20261022-run2",
    "question-bank-token-phase-2-4d-b-20261022-run3",
)
DEFAULT_REVIEW_DIR = (
    PROJECT_ROOT
    / "storage/reports/question-bank-token-phase-2-4d-b-protocol-v2-review-20261022"
)
PROTECTED_BASELINE_NAME = "protected-assets-before.json"


class Phase24DBProtocolReviewError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_protected_assets(
    baseline_path: Path = DEFAULT_REVIEW_DIR / PROTECTED_BASELINE_NAME,
    *,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase24DBProtocolReviewError(
            "Protected asset hash baseline is unreadable"
        ) from exc
    files = baseline.get("files")
    if not isinstance(files, dict):
        raise Phase24DBProtocolReviewError("Protected asset baseline has no file map")
    missing: list[str] = []
    changed: list[dict[str, str]] = []
    for relative, expected in files.items():
        path = project_root / relative
        if not path.is_file():
            missing.append(relative)
            continue
        actual = sha256_file(path)
        if actual != expected:
            changed.append(
                {"path": relative, "expected_sha256": expected, "actual_sha256": actual}
            )
    return {
        "status": "passed" if not missing and not changed else "failed",
        "algorithm": "sha256",
        "checked_file_count": len(files),
        "missing": missing,
        "changed": changed,
        "baseline_sha256": sha256_file(baseline_path),
    }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase24DBProtocolReviewError(f"Unreadable evidence file: {path}") from exc
    if not isinstance(value, dict):
        raise Phase24DBProtocolReviewError(f"Evidence file must be an object: {path}")
    return value


def _safe_final_output(smoke: dict[str, Any] | None) -> bool:
    if not smoke or smoke.get("execution_mode") != "real":
        return False
    checks = (
        "final_schema_passed",
        "assembler_passed",
        "strict_count_passed",
        "stack_boundary_passed",
        "duplicate_check_passed",
    )
    return all(smoke.get(check) == "passed" for check in checks)


def _safe_attempt(call: dict[str, Any]) -> dict[str, Any]:
    usage = call.get("token_usage")
    safe_usage = usage if isinstance(usage, dict) else {}
    return {
        "call": call.get("call"),
        "status": call.get("status"),
        "latency_ms": call.get("latency_ms"),
        "token_usage": {
            field: safe_usage.get(field)
            for field in ("input_tokens", "output_tokens", "total_tokens")
        },
        "token_usage_status": call.get("token_usage_status"),
        "failure_category": call.get("failure_category"),
        "exception_type": call.get("exception_type"),
        "http_status_code": call.get("http_status_code"),
    }


def _incident_kind(
    manifest: dict[str, Any], smoke: dict[str, Any] | None, calls: list[dict[str, Any]]
) -> tuple[str, list[str]]:
    if manifest.get("model") == "phase-2.4d-b-unconfigured" and not calls:
        return (
            "manifest_model_label_misconfiguration",
            ["model_label_unconfigured", "provider_calls_zero", "not_a_real_experiment"],
        )
    if smoke and smoke.get("execution_mode") == "fallback":
        return (
            "network_failures_then_fallback",
            [
                "final_output_fallback",
                "all_attempt_usage_unknown",
                "fallback_forbidden_for_prompt_evaluation",
            ],
        )
    if smoke and smoke.get("execution_mode") == "real":
        return (
            "timeout_then_real_success",
            [
                "failed_attempt_usage_unknown",
                "billing_usage_incomplete",
                "v1_smoke_usage_unknown",
                "smoke_only_not_a_paired_ab_result",
            ],
        )
    return "unclassified_blocking_event", ["insufficient_real_experiment_evidence"]


def build_blocking_event(run_dir: Path) -> dict[str, Any]:
    manifest_path = run_dir / "manifest.json"
    report_path = run_dir / "question-draft-token-report.json"
    audit_path = run_dir / "audit/executions.json"
    manifest = _load_json(manifest_path)
    report = _load_json(report_path)
    audit = _load_json(audit_path)
    smoke = audit.get("smoke") if isinstance(audit.get("smoke"), dict) else None
    raw_calls = audit.get("provider_calls")
    calls = raw_calls if isinstance(raw_calls, list) else []
    safe_calls = [_safe_attempt(call) for call in calls if isinstance(call, dict)]
    max_calls = manifest.get("protocol", {}).get("max_provider_calls", 62)
    accounting = account_execution_v2(
        safe_calls,
        final_execution_mode=smoke.get("execution_mode") if smoke else None,
        final_output_safe_valid=_safe_final_output(smoke),
        provider_call_limit=max_calls,
        terminal_status=smoke.get("terminal_status") if smoke else None,
    )
    incident_kind, reasons = _incident_kind(manifest, smoke, safe_calls)
    billing_status = accounting["billing_usage_completeness"]["status"]
    return {
        "record_type": "phase_2_4d_b_blocking_event",
        "source_run": run_dir.name,
        "source_protocol_version": manifest.get("protocol_version"),
        "source_status": manifest.get("status"),
        "source_stop_reason": report.get("stop_reason"),
        "source_evidence": {
            "manifest": {
                "path": manifest_path.relative_to(PROJECT_ROOT).as_posix(),
                "sha256": sha256_file(manifest_path),
            },
            "report": {
                "path": report_path.relative_to(PROJECT_ROOT).as_posix(),
                "sha256": sha256_file(report_path),
            },
            "execution_audit": {
                "path": audit_path.relative_to(PROJECT_ROOT).as_posix(),
                "sha256": sha256_file(audit_path),
            },
        },
        "provider": manifest.get("provider"),
        "model_label": manifest.get("model"),
        "incident_kind": incident_kind,
        "blocking_reasons": reasons,
        "provider_attempts": safe_calls,
        "protocol_v2_accounting_projection": accounting,
        "billing_usage_warning": (
            "BILLING USAGE INCOMPLETE: actual total token consumption is unknown."
            if billing_status == "incomplete"
            else None
        ),
        "prompt_v0_2_token_ab_eligibility": "excluded",
        "prompt_v0_2_quality_eligibility": "excluded",
        "fallback_content_used_for_evaluation": False,
        "historical_source_mutated": False,
        "interpretation_boundary": (
            "This is a new incident record and v2 accounting projection. It does not "
            "overwrite or change the v1 report's recorded outcome."
        ),
    }


def _line_number(path: Path, text: str) -> int | None:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if text in line:
            return number
    return None


def build_provider_client_audit() -> dict[str, Any]:
    client = PROJECT_ROOT / "app/agents/openai_compatible_client.py"
    base = PROJECT_ROOT / "app/agents/base.py"
    observability = PROJECT_ROOT / "app/services/provider_failure_observability.py"
    runner = PROJECT_ROOT / "app/services/question_draft_token_experiment.py"
    signature = inspect.signature(httpx.AsyncClient)

    def default(name: str) -> str | bool | None:
        value = signature.parameters[name].default
        if value is inspect.Parameter.empty:
            return None
        if isinstance(value, (str, bool, int, float)) or value is None:
            return value
        return str(value)

    return {
        "record_type": "phase_2_4d_b_provider_client_static_audit",
        "audit_scope": "source_and_sanitized_run_metadata_only",
        "sensitive_data_persisted": False,
        "source_files": {
            path.relative_to(PROJECT_ROOT).as_posix(): sha256_file(path)
            for path in (client, base, observability, runner)
        },
        "timeout_layers": {
            "provider_request_seconds": 60,
            "provider_request_source": {
                "path": client.relative_to(PROJECT_ROOT).as_posix(),
                "line": _line_number(client, "timeout=60"),
            },
            "variant_deadline_seconds": 120,
            "variant_deadline_source": {
                "path": runner.relative_to(PROJECT_ROOT).as_posix(),
                "line": _line_number(runner, "asyncio.timeout"),
            },
            "scope": (
                "the 60-second timeout applies to each HTTP attempt; the 120-second "
                "deadline applies to the whole variant execution"
            ),
        },
        "retry_ownership": {
            "owner": "BaseAgent.run_with_fallback",
            "configured_max_attempts": 2,
            "provider_client_retry_loop_present": False,
            "harness_retry_loop_present": False,
            "source": {
                "path": base.relative_to(PROJECT_ROOT).as_posix(),
                "line": _line_number(base, "for attempt in range"),
            },
        },
        "remote_protocol_error": {
            "classification": "network",
            "classification_only_not_root_cause": True,
            "source": {
                "path": observability.relative_to(PROJECT_ROOT).as_posix(),
                "line": _line_number(observability, "httpx.RemoteProtocolError"),
            },
        },
        "http_connection_pool_lifecycle": {
            "injected_client": (
                "caller-owned AsyncClient is reused according to caller lifecycle"
            ),
            "default_client": (
                "a new AsyncClient context is created and closed inside each generate_json call"
            ),
            "cross_attempt_pool_reuse_on_default_path": False,
            "source": {
                "path": client.relative_to(PROJECT_ROOT).as_posix(),
                "line": _line_number(client, "async with httpx.AsyncClient"),
            },
        },
        "transport_configuration_sources": {
            "project_explicit_proxy": None,
            "project_explicit_tls_verify_or_ca": None,
            "project_explicit_http2": None,
            "project_explicit_keepalive_limits": None,
            "effective_source": (
                "installed httpx defaults and environment handling, or caller settings "
                "when an AsyncClient is injected"
            ),
            "current_offline_runtime": {
                "httpx_version": httpx.__version__,
                "trust_env_default": default("trust_env"),
                "verify_default": default("verify"),
                "http1_default": default("http1"),
                "http2_default": default("http2"),
                "proxy_default": default("proxy"),
                "limits_default": default("limits"),
            },
        },
        "max_tokens": {
            "request_field_present": False,
            "frozen_protocol_value": None,
            "provable_per_request_output_token_upper_bound": False,
            "decision": (
                "do not add max_tokens in protocol v2; adding it later creates a new "
                "fixed protocol and requires the complete experiment to be rerun"
            ),
        },
        "root_cause_conclusion": "insufficient_evidence",
        "root_cause_limits": [
            "no Provider-side trace",
            "no sanitized proxy/TLS snapshot from the failing process",
            "no transport-level connection lifecycle trace",
            "no request identifier in the recorded failures",
        ],
    }


def build_review(*, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    report_root = project_root / "storage/reports"
    events = [build_blocking_event(report_root / name) for name in RUN_NAMES]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "record_type": "phase_2_4d_b_offline_protocol_review",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "network_accessed": False,
        "run4_created": False,
        "historical_reports_rewritten": False,
        "events": events,
        "provider_client_audit": build_provider_client_audit(),
        "protocol_v2": protocol_v2_snapshot(),
        "protected_assets": verify_protected_assets(project_root=project_root),
    }


def write_review_artifacts(output_dir: Path = DEFAULT_REVIEW_DIR) -> dict[str, Path]:
    resolved = output_dir.resolve()
    historical = [
        (PROJECT_ROOT / "storage/reports" / name).resolve() for name in RUN_NAMES
    ]
    if any(resolved == path or resolved.is_relative_to(path) for path in historical):
        raise Phase24DBProtocolReviewError(
            "Review output must not overlap a historical run directory"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    review = build_review()
    files = {
        "events": output_dir / "blocking-events.json",
        "provider_audit": output_dir / "provider-client-audit.json",
        "protocol": output_dir / "protocol-v2.json",
        "review": output_dir / "offline-review.json",
    }
    payloads = {
        "events": {
            "protocol_version": PROTOCOL_VERSION,
            "events": review["events"],
        },
        "provider_audit": review["provider_client_audit"],
        "protocol": review["protocol_v2"],
        "review": review,
    }
    for key, path in files.items():
        path.write_text(
            json.dumps(payloads[key], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return files
