from __future__ import annotations

from typing import Any

import httpx

from app.schemas import OllamaGenerateResponse


class OllamaClientError(RuntimeError):
    """Raised when Ollama API call fails."""


class OllamaClient:
    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _generate(self, model: str, prompt: str, as_json: bool) -> OllamaGenerateResponse:
        url = f"{self.base_url}/api/generate"
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if as_json:
            payload["format"] = "json"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
        except httpx.RequestError as exc:
            raise OllamaClientError(
                "Ollama is not available. Make sure Ollama is running on the host machine and required models are installed."
            ) from exc

        if response.status_code >= 400:
            body_preview = response.text[:400]
            lower_preview = body_preview.lower()
            if response.status_code == 404 or ("model" in lower_preview and "not found" in lower_preview):
                raise OllamaClientError(f"Model '{model}' is not available in Ollama. Run: ollama pull {model}")
            raise OllamaClientError(
                f"Ollama request failed with status {response.status_code}: {body_preview}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise OllamaClientError("Ollama returned a non-JSON response payload.") from exc

        text = data.get("response")
        if not isinstance(text, str):
            raise OllamaClientError("Ollama response does not contain a text field 'response'.")

        return OllamaGenerateResponse(
            model=str(data.get("model") or model),
            response=text,
            done=bool(data.get("done", False)),
            raw=data,
        )

    async def generate_json(self, model: str, prompt: str) -> OllamaGenerateResponse:
        return await self._generate(model=model, prompt=prompt, as_json=True)

    async def generate_text(self, model: str, prompt: str) -> OllamaGenerateResponse:
        return await self._generate(model=model, prompt=prompt, as_json=False)
