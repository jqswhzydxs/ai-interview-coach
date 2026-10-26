from datetime import datetime, timezone

from app.agents.base import BaseAgent
from app.schemas.prep_package import MatchReport


class MatchingAgent(BaseAgent):
    name = "matching_agent"
    prompt_version = "matching_agent_v0.1"

    async def run(self, input_data: dict) -> dict:
        return await self.run_with_fallback(
            input_data,
            MatchReport,
            self._rule_based_report,
        )

    def _rule_based_report(self) -> dict:
        return {
            "schema_version": "v0.1",
            "generated_at": datetime.now(timezone.utc),
            "agent_name": self.name,
            "prompt_version": self.prompt_version,
            "overall_score": 82,
            "summary": "候选人与后端岗位整体匹配，项目深度和量化表达仍需加强。",
            "matched_strengths": ["具备 Python/FastAPI 后端项目经验"],
            "missing_capabilities": ["系统设计表达需要补强"],
            "expression_issues": ["项目影响缺少量化指标"],
            "risk_points": ["回答可能停留在实现描述，缺少取舍"],
            "resume_suggestions": [
                {
                    "target_section": "projects",
                    "problem": "项目成果不够量化",
                    "suggestion": "补充性能、规模或稳定性指标",
                    "example_rewrite": "将接口延迟、并发量或数据规模写清楚",
                    "evidence_refs": [
                        {"source_type": "resume", "summary": "简历项目经历"}
                    ],
                }
            ],
            "preparation_priorities": ["项目深挖", "数据库事务", "接口设计"],
            "evidence_refs": [
                {"source_type": "resume", "summary": "简历技能和项目"},
                {"source_type": "jd", "summary": "岗位后端要求"},
            ],
        }
