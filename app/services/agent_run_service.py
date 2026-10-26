from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.db.models.agent_run import AgentRun, AgentRunStep

if TYPE_CHECKING:
    from app.agents.base import AgentExecutionMetadata


SENSITIVE_LOG_KEYS = {
    "raw_text",
    "resume_text",
    "jd_text",
    "experience_text",
    "user_answer",
    "system_prompt",
    "user_prompt",
    "raw_response",
    "resume_profile",
    "jd_profile",
    "experience_profiles",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def summarize_payload(payload: object) -> dict:
    if get_settings().save_full_llm_logs:
        if isinstance(payload, dict):
            return {"payload": _redact_sensitive(payload)}
        return {"payload": _value_descriptor(payload)}
    if isinstance(payload, dict):
        summary = {"keys": sorted(str(key) for key in payload.keys())}
        preparation_goal = payload.get("preparation_goal")
        if isinstance(preparation_goal, str):
            summary["preparation_goal"] = preparation_goal
        return summary
    return {"type": type(payload).__name__}


def _redact_sensitive(payload: object, *, key: str | None = None) -> object:
    if key is not None and _is_sensitive_key(key):
        return _value_descriptor(payload)
    if isinstance(payload, dict):
        return {
            str(item_key): _redact_sensitive(value, key=str(item_key))
            for item_key, value in payload.items()
        }
    if isinstance(payload, list):
        return [_redact_sensitive(item) for item in payload]
    return payload


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return (
        normalized in SENSITIVE_LOG_KEYS
        or "api_key" in normalized
        or "password" in normalized
        or "secret" in normalized
        or "authorization" in normalized
    )


def _value_descriptor(value: object) -> dict:
    if isinstance(value, str):
        return {"redacted": True, "type": "str", "length": len(value)}
    if isinstance(value, dict):
        return {
            "redacted": True,
            "type": "dict",
            "keys": sorted(str(item_key) for item_key in value.keys()),
        }
    if isinstance(value, list):
        return {"redacted": True, "type": "list", "length": len(value)}
    return {"redacted": True, "type": type(value).__name__}


class AgentRunService:
    def create_run(
        self,
        db: Session,
        *,
        user_id: UUID,
        run_type: str,
        provider: str,
        prompt_version: str | None,
        input_summary: dict,
        model_name: str | None,
    ) -> AgentRun:
        run = AgentRun(
            user_id=user_id,
            run_type=run_type,
            status="running",
            provider=provider,
            execution_mode="mock" if provider == "mock" else "real",
            model_name=model_name,
            prompt_version=prompt_version,
            input_summary_json=input_summary,
            output_summary_json={},
        )
        db.add(run)
        db.flush()
        return run

    def add_step(
        self,
        db: Session,
        *,
        run: AgentRun,
        step_order: int,
        agent_name: str,
        action_type: str,
        input_json: dict,
        output_json: dict,
        status: str,
        error_message: str | None,
        latency_ms: int | None,
    ) -> AgentRunStep:
        step = AgentRunStep(
            agent_run_id=run.id,
            step_order=step_order,
            agent_name=agent_name,
            action_type=action_type,
            input_json=input_json,
            output_json=output_json,
            status=status,
            error_message=error_message,
            latency_ms=latency_ms,
        )
        db.add(step)
        db.flush()
        return step

    def apply_execution_metadata(
        self,
        run: AgentRun,
        metadata: "AgentExecutionMetadata",
    ) -> None:
        run.provider = metadata.provider
        run.execution_mode = metadata.execution_mode
        run.model_name = metadata.model_name
        run.prompt_version = metadata.prompt_version
        run.real_call_count = metadata.real_call_count
        run.retry_count = metadata.retry_count
        run.latency_ms = metadata.latency_ms
        run.input_tokens = metadata.input_tokens
        run.output_tokens = metadata.output_tokens
        run.total_tokens = metadata.total_tokens
        run.fallback_reason_json = metadata.fallback_reason
        run.failure_counts_json = metadata.failure_counts

    def mark_succeeded(self, run: AgentRun, output_summary: dict) -> None:
        run.status = "succeeded"
        run.output_summary_json = output_summary
        run.finished_at = utc_now()

    def mark_failed(self, run: AgentRun, error_message: str) -> None:
        run.status = "failed"
        run.error_message = error_message
        run.finished_at = utc_now()

    def get_metrics(
        self,
        db: Session,
        *,
        run_ids: list[UUID] | None = None,
    ) -> dict:
        query = select(AgentRun)
        if run_ids is not None:
            if not run_ids:
                return self._empty_metrics()
            query = query.where(AgentRun.id.in_(run_ids))
        runs = list(db.scalars(query).all())
        if not runs:
            return self._empty_metrics()

        execution_modes = {"mock": 0, "real": 0, "fallback": 0}
        failure_types: dict[str, int] = {}
        for run in runs:
            execution_modes[run.execution_mode] = execution_modes.get(run.execution_mode, 0) + 1
            for failure_type, count in (run.failure_counts_json or {}).items():
                failure_types[str(failure_type)] = failure_types.get(str(failure_type), 0) + int(
                    count
                )

        real_attempted = sum(
            1 for run in runs if run.execution_mode in {"real", "fallback"}
        )
        real_succeeded = sum(
            1
            for run in runs
            if run.execution_mode == "real"
            and run.status == "succeeded"
        )
        fallback_runs = sum(1 for run in runs if run.execution_mode == "fallback")
        latencies = [run.latency_ms for run in runs if run.latency_ms is not None]
        return {
            "total_runs": len(runs),
            "succeeded_runs": sum(1 for run in runs if run.status == "succeeded"),
            "failed_runs": sum(1 for run in runs if run.status == "failed"),
            "execution_modes": execution_modes,
            "real_attempted_runs": real_attempted,
            "real_succeeded_runs": real_succeeded,
            "real_success_rate": _rate(real_succeeded, real_attempted),
            "fallback_runs": fallback_runs,
            "fallback_rate": _rate(fallback_runs, real_attempted),
            "real_call_count": sum(run.real_call_count for run in runs),
            "retry_count": sum(run.retry_count for run in runs),
            "failure_types": dict(sorted(failure_types.items())),
            "latency_ms": {
                "total": sum(latencies),
                "average": round(sum(latencies) / len(latencies), 2) if latencies else None,
            },
            "token_usage": {
                "input_tokens": sum(run.input_tokens or 0 for run in runs),
                "output_tokens": sum(run.output_tokens or 0 for run in runs),
                "total_tokens": sum(run.total_tokens or 0 for run in runs),
            },
        }

    def serialize_observability(self, run: AgentRun) -> dict:
        return {
            "agent_run_id": str(run.id),
            "run_type": run.run_type,
            "status": run.status,
            "execution_mode": run.execution_mode,
            "provider": run.provider,
            "model": run.model_name,
            "prompt_version": run.prompt_version,
            "real_call_count": run.real_call_count,
            "retry_count": run.retry_count,
            "latency_ms": run.latency_ms,
            "token_usage": {
                "input_tokens": run.input_tokens,
                "output_tokens": run.output_tokens,
                "total_tokens": run.total_tokens,
            },
            "fallback_reason": run.fallback_reason_json or None,
            "failure_types": run.failure_counts_json or {},
        }

    def _empty_metrics(self) -> dict:
        return {
            "total_runs": 0,
            "succeeded_runs": 0,
            "failed_runs": 0,
            "execution_modes": {"mock": 0, "real": 0, "fallback": 0},
            "real_attempted_runs": 0,
            "real_succeeded_runs": 0,
            "real_success_rate": None,
            "fallback_runs": 0,
            "fallback_rate": None,
            "real_call_count": 0,
            "retry_count": 0,
            "failure_types": {},
            "latency_ms": {"total": 0, "average": None},
            "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        }

    def get_run_detail(self, db: Session, agent_run_id: UUID) -> dict:
        run = db.get(AgentRun, agent_run_id)
        if run is None:
            raise AppError(ErrorCode.NOT_FOUND, "Agent run not found", status_code=404)

        steps = db.scalars(
            select(AgentRunStep)
            .where(AgentRunStep.agent_run_id == agent_run_id)
            .order_by(AgentRunStep.step_order)
        ).all()
        return {
            "agent_run_id": run.id,
            "run_type": run.run_type,
            "status": run.status,
            "execution_mode": run.execution_mode,
            "provider": run.provider,
            "model_name": run.model_name,
            "prompt_version": run.prompt_version,
            "real_call_count": run.real_call_count,
            "retry_count": run.retry_count,
            "latency_ms": run.latency_ms,
            "token_usage": {
                "input_tokens": run.input_tokens,
                "output_tokens": run.output_tokens,
                "total_tokens": run.total_tokens,
            },
            "fallback_reason": run.fallback_reason_json or None,
            "failure_types": run.failure_counts_json or {},
            "input_summary": run.input_summary_json,
            "output_summary": run.output_summary_json,
            "error_message": run.error_message,
            "created_at": run.created_at,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "steps": [
                {
                    "agent_run_step_id": step.id,
                    "step_order": step.step_order,
                    "agent_name": step.agent_name,
                    "action_type": step.action_type,
                    "status": step.status,
                    "error_message": step.error_message,
                    "latency_ms": step.latency_ms,
                    "created_at": step.created_at,
                }
                for step in steps
            ],
        }


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)
