from __future__ import annotations

import httpx

from app.schemas import OllamaGenerateResponse


class OllamaClientError(RuntimeError):
    """Raised when Ollama API call fails."""


class OllamaClient:
    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def generate_json(self, model: str, prompt: str) -> OllamaGenerateResponse:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
        except httpx.RequestError as exc:
            raise OllamaClientError(
                "Ollama is not available. Make sure Ollama is running on the host machine "
                "and qwen3:8b is installed."
            ) from exc

        if response.status_code >= 400:
            body_preview = response.text[:300]
            if response.status_code == 404 or "model" in body_preview.lower() and "not found" in body_preview.lower():
                raise OllamaClientError(
                    f"Model '{model}' is not available in Ollama. Run: ollama pull {model}"
                )
            raise OllamaClientError(
                f"Ollama request failed with status {response.status_code}: {body_preview}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise OllamaClientError("Ollama returned a non-JSON response.") from exc

        text = data.get("response")
        if not isinstance(text, str) or not text.strip():
            raise OllamaClientError("Ollama response does not contain 'response' text.")

        return OllamaGenerateResponse(
            model=str(data.get("model") or model),
            response=text,
            done=bool(data.get("done", False)),
            raw=data,
        )
