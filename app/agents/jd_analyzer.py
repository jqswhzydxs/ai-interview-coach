from datetime import datetime, timezone

from app.agents.base import BaseAgent
from app.schemas.job_description import JDProfile


class JDAnalyzerAgent(BaseAgent):
    name = "jd_analyzer"
    prompt_version = "jd_analyzer_v0.1"

    async def run(self, input_data: dict) -> dict:
        return await self.run_with_fallback(
            input_data,
            JDProfile,
            lambda: self._rule_based_profile(input_data),
        )

    def _rule_based_profile(self, input_data: dict) -> dict:
        raw_text = input_data.get("raw_text", "")
        keywords = []
        for keyword in ["Python", "FastAPI", "PostgreSQL", "API", "SQLAlchemy"]:
            if keyword.lower() in raw_text.lower():
                keywords.append(keyword)
        if not keywords:
            keywords = ["backend"]

        return {
            "schema_version": "v0.1",
            "generated_at": datetime.now(timezone.utc),
            "agent_name": self.name,
            "prompt_version": self.prompt_version,
            "job_title": input_data.get("title") or "Backend Engineer",
            "company_name": input_data.get("company_name"),
            "job_level": None,
            "core_responsibilities": ["后端接口设计与实现"],
            "hard_requirements": keywords,
            "bonus_points": [],
            "tech_keywords": keywords,
            "backend_dimensions": ["language", "web_framework", "database"],
            "interview_focuses": ["项目经验", "接口设计", "数据库实践"],
            "evidence_refs": [{"source_type": "jd", "summary": "来源于岗位描述材料"}],
        }
