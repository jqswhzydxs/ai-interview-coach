from uuid import UUID

from app.agents.base import BaseAgent
from app.agents.source_quality import fallback_source_names
from app.schemas.memory import MemoryUpdate


class MemoryAgent(BaseAgent):
    name = "memory_agent"
    prompt_version = "memory_agent_v0.1"

    async def run(self, input_data: dict) -> dict:
        degraded_sources = fallback_source_names(input_data)
        evaluation = input_data.get("answer_evaluation") or {}
        if isinstance(evaluation, dict) and (
            evaluation.get("evaluation_mode") == "degraded"
            or evaluation.get("score_available") is False
        ):
            degraded_sources = sorted({*degraded_sources, "answer_evaluation"})

        if degraded_sources:
            return self.finish_policy_fallback(
                lambda: self._skip_memory_update(
                    "degraded_upstream_source",
                    degraded_sources,
                ),
                code="memory_write_blocked",
                degraded_sources=degraded_sources,
            )

        if not self.should_use_real_llm():
            fallback_factory = self._rule_based_memory_update
        else:
            fallback_factory = lambda: self._skip_memory_update(
                "memory_provider_fallback",
                ["memory_agent"],
            )
        return await self.run_with_fallback(
            input_data,
            MemoryUpdate,
            fallback_factory,
        )

    def _rule_based_memory_update(self) -> dict:
        return {
            "write_decision": "write",
            "skip_reason": None,
            "memory_items": [
                {
                    "memory_type": "weakness",
                    "category": "answer_specificity",
                    "content": "回答项目经历时需要补充量化指标和技术取舍。",
                    "evidence": [
                        {
                            "source_type": "answer",
                            "summary": "单题评价指出项目细节和指标不足",
                        }
                    ],
                    "confidence": 0.85,
                    "source_type": "answer_evaluation",
                    "source_id": UUID("00000000-0000-0000-0000-000000000001"),
                    "status": "active",
                }
            ],
        }

    def _skip_memory_update(self, code: str, sources: list[str]) -> dict:
        return {
            "write_decision": "skip",
            "skip_reason": {
                "code": code,
                "degraded_sources": sorted(set(sources)),
            },
            "memory_items": [],
        }
