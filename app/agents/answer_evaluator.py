from datetime import datetime, timezone

from app.agents.base import BaseAgent


class AnswerEvaluatorAgent(BaseAgent):
    name = "answer_evaluator"
    prompt_version = "answer_evaluator_v0.1"

    async def run(self, input_data: dict) -> dict:
        question_text = input_data.get("question_text", "请说明你的后端项目。")
        user_answer = input_data.get("user_answer", "")
        return {
            "schema_version": "v0.1",
            "generated_at": datetime.now(timezone.utc),
            "agent_name": self.name,
            "prompt_version": self.prompt_version,
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
            "overall_comment": "回答方向正确，但需要补充真实项目指标和关键技术取舍。",
            "strengths": ["能说明使用的后端技术栈"],
            "improvement_points": ["补充接口规模、性能指标或数据库设计取舍"],
            "risks": ["如果缺少具体数据，面试官可能继续追问真实性和深度"],
            "improved_answer": "我在项目中负责 FastAPI 接口和 PostgreSQL 数据设计，并重点处理了接口分层、事务边界和错误处理。",
            "follow_up_questions": ["你当时如何设计数据库事务边界？"],
            "next_practice_suggestion": "下一题练习项目深挖，重点准备技术取舍和量化结果。",
            "memory_update": {
                "content": "回答需要补充项目指标和技术取舍",
                "confidence": 0.82,
            },
        }
