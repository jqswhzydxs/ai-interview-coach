from datetime import datetime, timezone

from app.agents.base import BaseAgent


class ExperienceAnalyzerAgent(BaseAgent):
    name = "experience_analyzer"
    prompt_version = "experience_analyzer_v0.1"

    async def run(self, input_data: dict) -> dict:
        raw_text = input_data.get("raw_text", "")
        topics = []
        for keyword in ["FastAPI", "database", "transaction", "API", "PostgreSQL"]:
            if keyword.lower() in raw_text.lower():
                topics.append(keyword)
        if not topics:
            topics = ["backend"]

        return {
            "schema_version": "v0.1",
            "generated_at": datetime.now(timezone.utc),
            "agent_name": self.name,
            "prompt_version": self.prompt_version,
            "source_summary": "基于用户提供的面经材料生成的摘要",
            "frequent_questions": ["请展开说明你的后端项目实现细节"],
            "frequent_topics": topics,
            "follow_up_patterns": ["围绕项目取舍和数据库一致性继续追问"],
            "jd_related_points": topics,
            "resume_related_points": ["项目细节"],
            "evidence_refs": [{"source_type": "experience", "summary": "来源于用户面经材料"}],
        }
