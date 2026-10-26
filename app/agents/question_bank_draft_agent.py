from app.agents.base import BaseAgent
from app.agents.question_bank_agent import QuestionBankAgent
from app.agents.question_bank_assembler import QuestionBankAssembler
from app.schemas.question_draft import QuestionDraftBank


class QuestionBankDraftAgent(BaseAgent):
    name = "question_bank_draft_agent"
    prompt_version = "question_bank_draft_agent_v0.1"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._safe_fallback_agent = QuestionBankAgent(llm_client=self.llm_client)
        self.assembler = QuestionBankAssembler(self._safe_fallback_agent)

    async def run(self, input_data: dict) -> dict:
        return await self.run_with_fallback(
            input_data,
            QuestionDraftBank,
            lambda: self._safe_fallback_agent._rule_based_question_bank(input_data),
            real_output_transform=lambda draft: self.assembler.assemble(
                draft,
                input_data,
            ),
        )
