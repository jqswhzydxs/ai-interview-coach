from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.db.models.agent_run import AgentRun, AgentRunStep


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def summarize_payload(payload: object) -> dict:
    if get_settings().save_full_llm_logs:
        return {"payload": payload}
    if isinstance(payload, dict):
        summary = {"keys": sorted(str(key) for key in payload.keys())}
        preparation_goal = payload.get("preparation_goal")
        if isinstance(preparation_goal, str):
            summary["preparation_goal"] = preparation_goal
        return summary
    return {"type": type(payload).__name__}


class AgentRunService:
    def create_run(
        self,
        db: Session,
        *,
        user_id: UUID,
        run_type: str,
        prompt_version: str | None,
        input_summary: dict,
        model_name: str | None,
    ) -> AgentRun:
        run = AgentRun(
            user_id=user_id,
            run_type=run_type,
            status="running",
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

    def mark_succeeded(self, run: AgentRun, output_summary: dict) -> None:
        run.status = "succeeded"
        run.output_summary_json = output_summary
        run.finished_at = utc_now()

    def mark_failed(self, run: AgentRun, error_message: str) -> None:
        run.status = "failed"
        run.error_message = error_message
        run.finished_at = utc_now()

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
            "model_name": run.model_name,
            "prompt_version": run.prompt_version,
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
