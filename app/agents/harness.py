from dataclasses import dataclass
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.agents.base import AgentExecutionMetadata, BaseAgent
from app.core.errors import AppError, ErrorCode
from app.services.agent_run_service import AgentRunService, summarize_payload

OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass(frozen=True)
class AgentExecutionResult(Generic[OutputT]):
    agent_run_id: UUID
    output: OutputT
    attempts: int
    metadata: AgentExecutionMetadata


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
        provider = getattr(agent.llm_client, "provider", "mock")
        run = self.run_service.create_run(
            db,
            user_id=user_id,
            run_type=run_type,
            provider=provider,
            prompt_version=agent.prompt_version,
            input_summary=summarize_payload(input_data),
            model_name=getattr(agent.llm_client, "model_name", None),
        )

        try:
            outcome = await agent.execute(input_data)
            output = output_schema.model_validate(outcome.output)
            self.run_service.apply_execution_metadata(run, outcome.metadata)
            self._add_execution_steps(
                db=db,
                run=run,
                agent=agent,
                input_data=input_data,
                output=output.model_dump(mode="json"),
                metadata=outcome.metadata,
            )
            self.run_service.mark_succeeded(run, summarize_payload(output.model_dump()))
            db.commit()
            return AgentExecutionResult(
                agent_run_id=run.id,
                output=output,
                attempts=max(1, outcome.metadata.real_call_count),
                metadata=outcome.metadata,
            )
        except ValidationError as exc:
            metadata = agent.last_execution
            needs_validation_step = True
            if metadata is not None:
                self.run_service.apply_execution_metadata(run, metadata)
                if metadata.execution_mode != "mock":
                    self._add_execution_steps(
                        db=db,
                        run=run,
                        agent=agent,
                        input_data=input_data,
                        output=None,
                        metadata=metadata,
                    )
                    needs_validation_step = metadata.execution_mode == "real"
            if needs_validation_step:
                self._add_failure_step(
                    db=db,
                    run=run,
                    agent=agent,
                    input_data=input_data,
                    step_order=self._next_step_order(metadata),
                    failure_type="schema",
                    action_type="output_validation",
                )
            failure_counts = dict(run.failure_counts_json or {})
            failure_counts["schema"] = failure_counts.get("schema", 0) + 1
            run.failure_counts_json = failure_counts
            self.run_service.mark_failed(run, "Agent output validation failed")
            db.commit()
            raise AppError(
                code=ErrorCode.AGENT_FAILED,
                message="Agent output validation failed",
                status_code=502,
                details={"failure_type": "schema", "error_count": len(exc.errors())},
            ) from exc
        except Exception as exc:
            metadata = agent.last_execution
            if metadata is not None:
                self.run_service.apply_execution_metadata(run, metadata)
                self._add_execution_steps(
                    db=db,
                    run=run,
                    agent=agent,
                    input_data=input_data,
                    output=None,
                    metadata=metadata,
                )
            self._add_failure_step(
                db=db,
                run=run,
                agent=agent,
                input_data=input_data,
                step_order=self._next_step_order(metadata),
                failure_type="provider",
                action_type="run",
            )
            failure_counts = dict(run.failure_counts_json or {})
            failure_counts["provider"] = failure_counts.get("provider", 0) + 1
            run.failure_counts_json = failure_counts
            self.run_service.mark_failed(run, "Agent execution failed")
            db.commit()
            raise AppError(
                code=ErrorCode.AGENT_FAILED,
                message="Agent execution failed",
                status_code=502,
                details={"failure_type": "provider"},
            ) from exc

    def _add_execution_steps(
        self,
        *,
        db: Session,
        run,
        agent: BaseAgent,
        input_data: dict,
        output: dict | None,
        metadata: AgentExecutionMetadata,
    ) -> None:
        input_summary = summarize_payload(input_data)
        if metadata.execution_mode == "mock":
            self.run_service.add_step(
                db,
                run=run,
                step_order=1,
                agent_name=agent.name,
                action_type="run",
                input_json=input_summary,
                output_json=summarize_payload(output) if output is not None else {},
                status="succeeded" if output is not None else "failed",
                error_message=None if output is not None else "Agent output validation failed",
                latency_ms=metadata.latency_ms,
            )
            return

        for trace in metadata.call_traces:
            token_usage = {
                "input_tokens": trace.input_tokens,
                "output_tokens": trace.output_tokens,
                "total_tokens": trace.total_tokens,
            }
            self.run_service.add_step(
                db,
                run=run,
                step_order=trace.attempt,
                agent_name=agent.name,
                action_type="llm_call",
                input_json=input_summary if trace.attempt == 1 else {},
                output_json={
                    "provider": metadata.provider,
                    "model": metadata.model_name,
                    "prompt_version": metadata.prompt_version,
                    "token_usage": token_usage,
                    "failure_type": trace.failure_type,
                },
                status=trace.status,
                error_message=(
                    f"LLM call failed: {trace.failure_type}"
                    if trace.failure_type is not None
                    else None
                ),
                latency_ms=trace.latency_ms,
            )

        if metadata.execution_mode == "fallback":
            self.run_service.add_step(
                db,
                run=run,
                step_order=len(metadata.call_traces) + 1,
                agent_name=agent.name,
                action_type="fallback",
                input_json={},
                output_json=(
                    summarize_payload(output)
                    if output is not None
                    else {"failure_type": "schema"}
                ),
                status="succeeded" if output is not None else "failed",
                error_message=None if output is not None else "Fallback output validation failed",
                latency_ms=metadata.fallback_latency_ms,
            )

    def _add_failure_step(
        self,
        *,
        db: Session,
        run,
        agent: BaseAgent,
        input_data: dict,
        step_order: int,
        failure_type: str,
        action_type: str,
    ) -> None:
        self.run_service.add_step(
            db,
            run=run,
            step_order=step_order,
            agent_name=agent.name,
            action_type=action_type,
            input_json=summarize_payload(input_data),
            output_json={"failure_type": failure_type},
            status="failed",
            error_message=f"Agent failed: {failure_type}",
            latency_ms=None,
        )

    @staticmethod
    def _next_step_order(metadata: AgentExecutionMetadata | None) -> int:
        if metadata is None:
            return 1
        if metadata.execution_mode == "mock":
            return 1
        return len(metadata.call_traces) + (2 if metadata.execution_mode == "fallback" else 1)
