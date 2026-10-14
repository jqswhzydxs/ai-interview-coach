from app.agents.base import BaseAgent


class QuestionBankAgent(BaseAgent):
    name = "question_bank_agent"
    prompt_version = "question_bank_agent_v0.1"

    def __init__(self, *args, total_count: int = 25, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.total_count = total_count

    async def run(self, input_data: dict) -> dict:
        self_intro_count = 8
        professional_count = 8
        behavior_count = max(0, self.total_count - self_intro_count - professional_count)
        return {
            "self_intro_questions": [
                self._question(index, "self_intro") for index in range(self_intro_count)
            ],
            "professional_questions": [
                self._question(index, "professional") for index in range(professional_count)
            ],
            "behavior_project_questions": [
                self._question(index, "behavior_project") for index in range(behavior_count)
            ],
            "total_count": self.total_count,
        }

    def _question(self, index: int, module: str) -> dict:
        module_prefix = {
            "self_intro": "self",
            "professional": "pro",
            "behavior_project": "beh",
        }[module]
        question_id = f"{module_prefix}-{index + 1:02d}"
        return {
            "question_id": question_id,
            "module": module,
            "question_text": self._question_text(module, index),
            "purpose": "评估候选人与后端岗位的匹配度",
            "difficulty": "medium" if index % 3 else "basic",
            "source_type": "mixed",
            "source_refs": [
                {"source_type": "resume", "summary": "来源于用户简历材料"},
                {"source_type": "jd", "summary": "来源于岗位描述材料"},
            ],
            "jd_keywords": ["Python", "FastAPI", "PostgreSQL"],
            "answer_framework": "先给结论，再说明背景、行动、结果和反思。",
            "star_template": "Situation: 背景；Task: 目标；Action: 行动；Result: 结果。",
            "scoring_anchors": [
                {
                    "name": "relevance",
                    "score": 8,
                    "max_score": 10,
                    "reason": "回答需要贴合岗位和简历项目",
                }
            ],
            "follow_up_questions": ["你在这个过程中做过哪些技术取舍？"],
            "preparation_advice": "准备一个真实项目例子，并补充量化指标。",
            "sort_order": index + 1,
        }

    def _question_text(self, module: str, index: int) -> str:
        if module == "self_intro":
            return f"请用 2 分钟介绍你的后端项目经历，并突出与岗位相关的能力。({index + 1})"
        if module == "professional":
            return f"请说明你在 FastAPI 或数据库实践中遇到的一个技术问题。({index + 1})"
        return f"请结合一个项目，说明你如何处理需求变化或技术取舍。({index + 1})"
