import httpx

from app.agents.openai_compatible_client import OpenAICompatibleChatClient


class KimiClient(OpenAICompatibleChatClient):
    provider = "kimi"
    default_base_url = "https://api.moonshot.cn/v1"

    def __init__(
        self,
        api_key: str,
        model_name: str,
        *,
        base_url: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model_name=model_name,
            base_url=base_url or self.default_base_url,
            http_client=http_client,
        )
