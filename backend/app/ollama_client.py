from app.schemas import OllamaChatMessage, OllamaChatResponse


class OllamaClient:
    """Stub client for future Ollama integration.

    The interface mirrors a future real HTTP client to make replacement easy.
    """

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def chat(self, model: str, prompt: str) -> OllamaChatResponse:
        # TODO: replace with real HTTP request to Ollama API.
        return OllamaChatResponse(
            model=model,
            message=OllamaChatMessage(
                role="assistant",
                content=f"Stub response from OllamaClient for prompt: {prompt[:120]}"
            ),
            done=True,
            raw={
                "provider": "ollama",
                "base_url": self.base_url,
                "stub": True
            }
        )

