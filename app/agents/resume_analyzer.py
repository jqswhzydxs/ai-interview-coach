from datetime import datetime, timezone
import re

from app.agents.base import BaseAgent
from app.schemas.resume import ResumeProfile


class ResumeAnalyzerAgent(BaseAgent):
    name = "resume_analyzer"
    prompt_version = "resume_analyzer_v0.1"

    async def run(self, input_data: dict) -> dict:
        return await self.run_with_fallback(
            input_data,
            ResumeProfile,
            lambda: self._rule_based_profile(input_data),
        )

    def _rule_based_profile(self, input_data: dict) -> dict:
        raw_text = input_data.get("raw_text", "")
        skills = [
            label
            for label, pattern in _LITERAL_SKILL_PATTERNS
            if re.search(pattern, raw_text, flags=re.IGNORECASE)
        ]

        return {
            "schema_version": "v0.1",
            "generated_at": datetime.now(timezone.utc),
            "agent_name": self.name,
            "prompt_version": self.prompt_version,
            "basic_info": {
                "summary": "降级解析仅保留原文中可直接识别的技能；其余事实未推断"
            },
            "education": [],
            "skills": skills,
            "projects": [],
            "work_experiences": [],
            "awards": [],
            "backend_tags": skills,
            "questionable_points": ["降级解析未推断项目、经历或成果"],
            "risk_points": [],
        }


_LITERAL_SKILL_PATTERNS = (
    ("Python", r"(?<![\w])Python(?![\w])"),
    ("FastAPI", r"(?<![\w])FastAPI(?![\w])"),
    ("Django", r"(?<![\w])Django(?![\w])"),
    ("Flask", r"(?<![\w])Flask(?![\w])"),
    ("SQLAlchemy", r"(?<![\w])SQLAlchemy(?![\w])"),
    ("Go", r"(?<![\w])Go(?![\w])"),
    ("Gin", r"(?<![\w])Gin(?![\w])"),
    ("gRPC", r"(?<![\w])gRPC(?![\w])"),
    ("Java", r"(?<![\w])Java(?![\w])"),
    ("Spring Boot", r"(?<![\w])Spring\s+Boot(?![\w])"),
    ("PostgreSQL", r"(?<![\w])PostgreSQL(?![\w])"),
    ("MySQL", r"(?<![\w])MySQL(?![\w])"),
    ("Redis", r"(?<![\w])Redis(?![\w])"),
    ("MongoDB", r"(?<![\w])MongoDB(?![\w])"),
    ("Kafka", r"(?<![\w])Kafka(?![\w])"),
    ("RabbitMQ", r"(?<![\w])RabbitMQ(?![\w])"),
    ("Docker", r"(?<![\w])Docker(?![\w])"),
    ("Kubernetes", r"(?<![\w])Kubernetes(?![\w])"),
    ("REST", r"(?<![\w])REST(?![\w])"),
)
