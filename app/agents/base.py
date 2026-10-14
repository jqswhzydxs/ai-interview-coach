from abc import ABC

from app.agents.llm_client import LLMClient


class BaseAgent(ABC):
    name: str
    prompt_version: str

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    async def run(self, input_data: dict) -> dict:
        raise NotImplementedError
