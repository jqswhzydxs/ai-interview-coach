from datetime import datetime, timezone

from app.agents.base import BaseAgent


class ResumeAnalyzerAgent(BaseAgent):
    name = "resume_analyzer"
    prompt_version = "resume_analyzer_v0.1"

    async def run(self, input_data: dict) -> dict:
        raw_text = input_data.get("raw_text", "")
        skills = []
        for keyword in ["Python", "FastAPI", "PostgreSQL", "SQLAlchemy"]:
            if keyword.lower() in raw_text.lower():
                skills.append(keyword)
        if not skills:
            skills = ["backend"]

        return {
            "schema_version": "v0.1",
            "generated_at": datetime.now(timezone.utc),
            "agent_name": self.name,
            "prompt_version": self.prompt_version,
            "basic_info": {"summary": "基于简历材料生成的候选人画像"},
            "education": [],
            "skills": skills,
            "projects": [
                {
                    "name": "简历项目",
                    "role": "候选人",
                    "background": "基于综合推断",
                    "tech_stack": skills,
                    "responsibilities": ["结合简历材料说明项目职责"],
                    "highlights": ["需要在后续回答中补充量化结果"],
                    "metrics": [],
                    "evidence_refs": [
                        {"source_type": "resume", "summary": "来源于用户简历材料"}
                    ],
                }
            ],
            "work_experiences": [],
            "awards": [],
            "backend_tags": skills,
            "questionable_points": ["项目指标需要进一步澄清"],
            "risk_points": ["表达可能缺少量化结果"],
        }
