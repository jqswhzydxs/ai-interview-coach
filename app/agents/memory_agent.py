from uuid import UUID

from app.agents.base import BaseAgent


class MemoryAgent(BaseAgent):
    name = "memory_agent"
    prompt_version = "memory_agent_v0.1"

    async def run(self, input_data: dict) -> dict:
        return {
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
            ]
        }
