from abc import ABC
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
import json
from time import perf_counter
from typing import Generic, Literal, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.agents.llm_client import (
    LLMJSONError,
    LLMRequest,
    LLMResponseError,
    TokenUsage,
)
from app.agents.llm_client import LLMClient
from app.agents.prompt_loader import load_prompt


OutputT = TypeVar("OutputT", bound=BaseModel)
ExecutionMode = Literal["mock", "real", "fallback"]
AttemptStatus = Literal["succeeded", "failed"]


class AgentOutputValidationError(ValueError):
    """A provider response is valid JSON but unsafe after deterministic validation."""


@dataclass(frozen=True)
class LLMCallTrace:
    attempt: int
    status: AttemptStatus
    latency_ms: int
    failure_type: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class AgentExecutionMetadata:
    execution_mode: ExecutionMode
    provider: str
    model_name: str | None
    prompt_version: str
    real_call_count: int
    retry_count: int
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    fallback_reason: dict
    failure_counts: dict[str, int]
    call_traces: tuple[LLMCallTrace, ...]
    fallback_latency_ms: int | None = None


@dataclass(frozen=True)
class AgentOutcome:
    output: dict
    metadata: AgentExecutionMetadata


class BaseAgent(ABC):
    name: str
    prompt_version: str

    def __init__(
        self,
        llm_client: LLMClient,
        *,
        use_real_llm: bool | None = None,
        max_real_llm_attempts: int = 2,
    ) -> None:
        if max_real_llm_attempts < 1:
            raise ValueError("max_real_llm_attempts must be at least 1")
        self.llm_client = llm_client
        self.use_real_llm = use_real_llm
        self.max_real_llm_attempts = max_real_llm_attempts
        self._last_execution: AgentExecutionMetadata | None = None

    async def run(self, input_data: dict) -> dict:
        raise NotImplementedError

    async def execute(self, input_data: dict) -> AgentOutcome:
        """Execute once; provider retry/fallback belongs to the agent, never the harness."""
        self._last_execution = None
        started_at = perf_counter()
        output = await self.run(input_data)
        metadata = self._last_execution
        if metadata is None:
            latency_ms = _elapsed_ms(started_at)
            is_real = self.should_use_real_llm()
            metadata = AgentExecutionMetadata(
                execution_mode="real" if is_real else "mock",
                provider=getattr(self.llm_client, "provider", "mock"),
                model_name=getattr(self.llm_client, "model_name", None),
                prompt_version=self.prompt_version,
                real_call_count=1 if is_real else 0,
                retry_count=0,
                latency_ms=latency_ms,
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                fallback_reason={},
                failure_counts={},
                call_traces=(
                    LLMCallTrace(attempt=1, status="succeeded", latency_ms=latency_ms),
                )
                if is_real
                else (),
            )
            self._last_execution = metadata
        return AgentOutcome(output=output, metadata=metadata)

    def should_use_real_llm(self) -> bool:
        if self.use_real_llm is not None:
            return self.use_real_llm
        return getattr(self.llm_client, "provider", "mock") != "mock"

    def finish_policy_fallback(
        self,
        fallback_factory: Callable[[], dict],
        *,
        code: str,
        degraded_sources: list[str] | None = None,
    ) -> dict:
        """Return an observable policy fallback without making a provider call."""
        overall_started_at = perf_counter()
        fallback_started_at = perf_counter()
        output = fallback_factory()
        reason = {
            "code": code,
            "failure_type": "policy",
            "stage": "quality_gate",
            "attempt": 0,
        }
        if degraded_sources:
            reason["degraded_sources"] = sorted(set(degraded_sources))
        self._last_execution = self._build_metadata(
            execution_mode="fallback",
            provider=getattr(self.llm_client, "provider", "mock"),
            model_name=getattr(self.llm_client, "model_name", None),
            overall_started_at=overall_started_at,
            traces=[],
            failures=[reason],
            fallback_reason=reason,
            fallback_latency_ms=_elapsed_ms(fallback_started_at),
        )
        return output

    @property
    def last_execution(self) -> AgentExecutionMetadata | None:
        return self._last_execution

    async def run_with_fallback(
        self,
        input_data: dict,
        output_schema: type[OutputT],
        fallback_factory: Callable[[], dict],
        *,
        real_output_transform: Callable[[OutputT], dict] | None = None,
    ) -> dict:
        """Run the sole retry loop and return one schema-ready real/mock/fallback output."""
        overall_started_at = perf_counter()
        provider = getattr(self.llm_client, "provider", "mock")
        model_name = getattr(self.llm_client, "model_name", None)

        if not self.should_use_real_llm():
            output = fallback_factory()
            self._last_execution = AgentExecutionMetadata(
                execution_mode="mock",
                provider=provider,
                model_name=model_name,
                prompt_version=self.prompt_version,
                real_call_count=0,
                retry_count=0,
                latency_ms=_elapsed_ms(overall_started_at),
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                fallback_reason={},
                failure_counts={},
                call_traces=(),
            )
            return output

        traces: list[LLMCallTrace] = []
        failures: list[dict] = []
        try:
            request = self._build_request(input_data, output_schema)
        except Exception as exc:
            reason = _safe_failure_reason(exc, attempt=0, stage="prompt_build")
            return self._finish_fallback(
                fallback_factory=fallback_factory,
                overall_started_at=overall_started_at,
                provider=provider,
                model_name=model_name,
                traces=traces,
                failures=[reason],
            )

        for attempt in range(1, self.max_real_llm_attempts + 1):
            call_started_at = perf_counter()
            response_usage: TokenUsage | None = None
            try:
                response = await self.llm_client.generate_json(request)
                response_usage = response.usage
                output = output_schema.model_validate(response.content)
                transformed_output = (
                    real_output_transform(output)
                    if real_output_transform is not None
                    else output.model_dump(mode="json")
                )
                traces.append(
                    _trace_from_usage(
                        attempt=attempt,
                        status="succeeded",
                        latency_ms=_elapsed_ms(call_started_at),
                        usage=response_usage,
                    )
                )
                metadata = self._build_metadata(
                    execution_mode="real",
                    provider=provider,
                    model_name=model_name,
                    overall_started_at=overall_started_at,
                    traces=traces,
                    failures=failures,
                    fallback_reason={},
                )
                self._last_execution = metadata
                return transformed_output
            except Exception as exc:
                response_usage = response_usage or getattr(exc, "usage", None)
                reason = _safe_failure_reason(exc, attempt=attempt)
                failures.append(reason)
                traces.append(
                    _trace_from_usage(
                        attempt=attempt,
                        status="failed",
                        latency_ms=_elapsed_ms(call_started_at),
                        usage=response_usage,
                        failure_type=reason["failure_type"],
                    )
                )

        return self._finish_fallback(
            fallback_factory=fallback_factory,
            overall_started_at=overall_started_at,
            provider=provider,
            model_name=model_name,
            traces=traces,
            failures=failures,
        )

    def _build_request(
        self,
        input_data: dict,
        output_schema: type[OutputT],
    ) -> LLMRequest:
        prompt_name, prompt_version = self.prompt_version.rsplit("_", maxsplit=1)
        prompt = load_prompt(prompt_name, prompt_version)
        output_contract = json.dumps(output_schema.model_json_schema(), ensure_ascii=False)
        system_prompt = (
            f"{prompt.content}\n\n"
            "输出要求：只返回一个 JSON object，不要使用 Markdown 代码块或附加说明。"
            f"输出必须符合以下 JSON Schema：{output_contract}"
        )
        return LLMRequest(
            system_prompt=system_prompt,
            user_prompt=json.dumps(input_data, ensure_ascii=False, default=str),
            response_schema_name=output_schema.__name__,
            temperature=0.2,
        )

    def _finish_fallback(
        self,
        *,
        fallback_factory: Callable[[], dict],
        overall_started_at: float,
        provider: str,
        model_name: str | None,
        traces: list[LLMCallTrace],
        failures: list[dict],
    ) -> dict:
        fallback_started_at = perf_counter()
        output = fallback_factory()
        fallback_latency_ms = _elapsed_ms(fallback_started_at)
        self._last_execution = self._build_metadata(
            execution_mode="fallback",
            provider=provider,
            model_name=model_name,
            overall_started_at=overall_started_at,
            traces=traces,
            failures=failures,
            fallback_reason=failures[-1] if failures else {},
            fallback_latency_ms=fallback_latency_ms,
        )
        return output

    def _build_metadata(
        self,
        *,
        execution_mode: ExecutionMode,
        provider: str,
        model_name: str | None,
        overall_started_at: float,
        traces: list[LLMCallTrace],
        failures: list[dict],
        fallback_reason: dict,
        fallback_latency_ms: int | None = None,
    ) -> AgentExecutionMetadata:
        real_call_count = len(traces)
        return AgentExecutionMetadata(
            execution_mode=execution_mode,
            provider=provider,
            model_name=model_name,
            prompt_version=self.prompt_version,
            real_call_count=real_call_count,
            retry_count=max(0, real_call_count - 1),
            latency_ms=_elapsed_ms(overall_started_at),
            input_tokens=_sum_optional(trace.input_tokens for trace in traces),
            output_tokens=_sum_optional(trace.output_tokens for trace in traces),
            total_tokens=_sum_optional(trace.total_tokens for trace in traces),
            fallback_reason=fallback_reason,
            failure_counts=dict(Counter(item["failure_type"] for item in failures)),
            call_traces=tuple(traces),
            fallback_latency_ms=fallback_latency_ms,
        )


def _elapsed_ms(started_at: float) -> int:
    return max(0, int((perf_counter() - started_at) * 1000))


def _trace_from_usage(
    *,
    attempt: int,
    status: AttemptStatus,
    latency_ms: int,
    usage: TokenUsage | None,
    failure_type: str | None = None,
) -> LLMCallTrace:
    return LLMCallTrace(
        attempt=attempt,
        status=status,
        latency_ms=latency_ms,
        failure_type=failure_type,
        input_tokens=usage.input_tokens if usage is not None else None,
        output_tokens=usage.output_tokens if usage is not None else None,
        total_tokens=usage.total_tokens if usage is not None else None,
    )


def _safe_failure_reason(
    exc: Exception,
    *,
    attempt: int,
    stage: str | None = None,
) -> dict:
    if isinstance(exc, AgentOutputValidationError):
        return {
            "code": "output_transform_validation_failed",
            "failure_type": "schema",
            "stage": stage or "output_transform",
            "attempt": attempt,
        }
    if isinstance(exc, ValidationError):
        return {
            "code": "schema_validation_failed",
            "failure_type": "schema",
            "stage": stage or "schema_validation",
            "attempt": attempt,
        }
    if isinstance(exc, LLMJSONError) or isinstance(exc, json.JSONDecodeError):
        return {
            "code": "invalid_json",
            "failure_type": "json",
            "stage": stage or "response_parse",
            "attempt": attempt,
        }
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return {
            "code": "provider_timeout",
            "failure_type": "timeout",
            "stage": stage or "provider_call",
            "attempt": attempt,
        }
    if isinstance(exc, LLMResponseError):
        failure_type = exc.failure_type
    else:
        failure_type = "provider"
    return {
        "code": "provider_error" if stage is None else "agent_preparation_failed",
        "failure_type": failure_type,
        "stage": stage or "provider_call",
        "attempt": attempt,
    }


def _sum_optional(values) -> int | None:
    present = [value for value in values if value is not None]
    return sum(present) if present else None
