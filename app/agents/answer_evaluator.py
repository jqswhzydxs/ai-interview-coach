from datetime import datetime, timezone

from app.agents.base import BaseAgent
from app.agents.source_quality import (
    aggregate_source_quality,
    fallback_source_names,
    source_record,
)
from app.schemas.evaluation import AnswerEvaluation


class AnswerEvaluatorAgent(BaseAgent):
    name = "answer_evaluator"
    prompt_version = "answer_evaluator_v0.1"

    async def run(self, input_data: dict) -> dict:
        degraded_sources = fallback_source_names(input_data)
        if degraded_sources:
            return self.finish_policy_fallback(
                lambda: self._degraded_evaluation(
                    input_data,
                    [f"upstream_fallback:{source}" for source in degraded_sources],
                ),
                code="degraded_upstream_source",
                degraded_sources=degraded_sources,
            )

        if not self.should_use_real_llm():
            output = await self.run_with_fallback(
                input_data,
                AnswerEvaluation,
                lambda: self._mock_evaluation(input_data),
            )
        else:
            output = await self.run_with_fallback(
                input_data,
                AnswerEvaluation,
                lambda: self._degraded_evaluation(
                    input_data,
                    ["evaluator_provider_fallback"],
                ),
            )

        if self.last_execution is not None and self.last_execution.execution_mode in {
            "mock",
            "real",
        }:
            effective_sources = dict(input_data.get("source_context") or {})
            effective_sources["answer_evaluation"] = source_record(
                self.last_execution.execution_mode
            )
            output["evaluation_mode"] = "standard"
            output["score_available"] = True
            output["source_quality"] = aggregate_source_quality(effective_sources)
            output["degradation_reasons"] = []
        return output

    def _mock_evaluation(self, input_data: dict) -> dict:
        question_text = input_data.get("question_text", "请说明你的后端项目。")
        user_answer = input_data.get("user_answer", "")
        return {
            "schema_version": "v0.1",
            "generated_at": datetime.now(timezone.utc),
            "agent_name": self.name,
            "prompt_version": self.prompt_version,
            "evaluation_mode": "standard",
            "score_available": True,
            "source_quality": aggregate_source_quality(input_data),
            "degradation_reasons": [],
            "question_id": input_data.get("question_id"),
            "question_text": question_text,
            "user_answer": user_answer,
            "total_score": 76,
            "dimension_scores": [
                {"name": "relevance", "score": 17, "max_score": 20, "reason": "回答基本贴题"},
                {
                    "name": "technical_accuracy",
                    "score": 19,
                    "max_score": 25,
                    "reason": "技术描述较准确，但细节不足",
                },
                {
                    "name": "project_specificity",
                    "score": 14,
                    "max_score": 20,
                    "reason": "项目细节和指标需要补充",
                },
                {"name": "structure", "score": 12, "max_score": 15, "reason": "结构基本清楚"},
                {"name": "communication", "score": 8, "max_score": 10, "reason": "表达简洁"},
                {"name": "risk_control", "score": 6, "max_score": 10, "reason": "需要避免泛泛而谈"},
            ],
            "overall_comment": "这是 mock 模式的确定性测试评价，不代表真实模型评分。",
            "strengths": ["回答包含后端实现信息"],
            "improvement_points": ["补充可由真实经历支持的约束、行动和结果"],
            "risks": ["避免把示例方案表述为已经发生的事实"],
            "improved_answer": "可按背景、个人任务、具体行动、可验证结果和复盘组织真实回答。",
            "follow_up_questions": ["哪一项结果可以由日志、指标或交付记录验证？"],
            "next_practice_suggestion": "下一题练习区分已知事实、个人行动和建议方案。",
            "memory_update": {
                "write_decision": "write",
                "content": "回答需要补充可验证结果和技术取舍",
                "confidence": 0.82,
            },
        }

    def _rule_based_evaluation(self, input_data: dict) -> dict:
        """Backward-compatible name for deterministic mock output, not real fallback."""
        return self._mock_evaluation(input_data)

    def _degraded_evaluation(self, input_data: dict, reasons: list[str]) -> dict:
        return {
            "schema_version": "v0.1",
            "generated_at": datetime.now(timezone.utc),
            "agent_name": self.name,
            "prompt_version": self.prompt_version,
            "evaluation_mode": "degraded",
            "score_available": False,
            "source_quality": "degraded",
            "degradation_reasons": reasons,
            "question_id": input_data.get("question_id"),
            "question_text": input_data.get("question_text", ""),
            "user_answer": input_data.get("user_answer", ""),
            "total_score": None,
            "dimension_scores": [],
            "overall_comment": "当前评价依赖降级来源，无法给出可信的精确分数。以下内容仅作一般性练习建议。",
            "strengths": [],
            "improvement_points": ["用结论、证据、个人行动和可验证结果重新组织回答"],
            "risks": ["在来源恢复前，不应把本次评价解释为能力测量结果"],
            "improved_answer": "建议使用真实经历按背景、任务、行动、结果和反思补充回答，不要加入未经证实的细节。",
            "follow_up_questions": ["你的回答中哪些内容有直接材料或结果证据？"],
            "next_practice_suggestion": "来源恢复后重新评价；当前仅练习回答结构和事实边界。",
            "memory_update": {
                "write_decision": "skip",
                "skip_reason": {
                    "code": "degraded_evaluation",
                    "reasons": reasons,
                },
                "confidence": 0,
            },
        }
