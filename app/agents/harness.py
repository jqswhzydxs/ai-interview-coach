from dataclasses import dataclass
from time import perf_counter
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.core.errors import AppError, ErrorCode
from app.services.agent_run_service import AgentRunService, summarize_payload

OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass(frozen=True)
class AgentExecutionResult(Generic[OutputT]):
    agent_run_id: UUID
    output: OutputT
    attempts: int


class AgentHarness:
    def __init__(self, run_service: AgentRunService | None = None) -> None:
        self.run_service = run_service or AgentRunService()

    async def run_agent(
        self,
        *,
        db: Session,
        user_id: UUID,
        run_type: str,
        agent: BaseAgent,
        input_data: dict,
        output_schema: type[OutputT],
    ) -> AgentExecutionResult[OutputT]:
        run = self.run_service.create_run(
            db,
            user_id=user_id,
            run_type=run_type,
            prompt_version=agent.prompt_version,
            input_summary=summarize_payload(input_data),
            model_name=getattr(agent.llm_client, "model_name", None),
        )
        last_error = ""

        for attempt in (1, 2):
            started_at = perf_counter()
            try:
                raw_output = await agent.run(input_data)
                output = output_schema.model_validate(raw_output)
                latency_ms = int((perf_counter() - started_at) * 1000)
                self.run_service.add_step(
                    db,
                    run=run,
                    step_order=attempt,
                    agent_name=agent.name,
                    action_type="run",
                    input_json=summarize_payload(input_data),
                    output_json=summarize_payload(output.model_dump()),
                    status="succeeded",
                    error_message=None,
                    latency_ms=latency_ms,
                )
                self.run_service.mark_succeeded(run, summarize_payload(output.model_dump()))
                db.commit()
                return AgentExecutionResult(
                    agent_run_id=run.id,
                    output=output,
                    attempts=attempt,
                )
            except ValidationError as exc:
                last_error = "Agent output validation failed"
                latency_ms = int((perf_counter() - started_at) * 1000)
                self.run_service.add_step(
                    db,
                    run=run,
                    step_order=attempt,
                    agent_name=agent.name,
                    action_type="run",
                    input_json=summarize_payload(input_data),
                    output_json={},
                    status="failed",
                    error_message=last_error,
                    latency_ms=latency_ms,
                )
                if attempt == 2:
                    self.run_service.mark_failed(run, last_error)
                    db.commit()
                    raise AppError(
                        code=ErrorCode.AGENT_FAILED,
                        message=last_error,
                        status_code=502,
                        details={"errors": exc.errors()},
                    ) from exc
            except Exception as exc:
                last_error = "Agent execution failed"
                latency_ms = int((perf_counter() - started_at) * 1000)
                self.run_service.add_step(
                    db,
                    run=run,
                    step_order=attempt,
                    agent_name=agent.name,
                    action_type="run",
                    input_json=summarize_payload(input_data),
                    output_json={},
                    status="failed",
                    error_message=last_error,
                    latency_ms=latency_ms,
                )
                self.run_service.mark_failed(run, last_error)
                db.commit()
                raise AppError(
                    code=ErrorCode.AGENT_FAILED,
                    message=last_error,
                    status_code=502,
                    details={"error": str(exc)},
                ) from exc

        raise AppError(
            code=ErrorCode.AGENT_FAILED,
            message=last_error or "Agent failed",
            status_code=502,
        )
