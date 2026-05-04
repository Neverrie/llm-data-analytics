from __future__ import annotations

import json
import re
from typing import Any

import httpx


class OpenRouterClientError(RuntimeError):
    """Raised when OpenRouter API call fails."""


class OpenRouterClient:
    def __init__(
        self,
        api_key: str | None,
        base_url: str = "https://openrouter.ai/api/v1",
        default_model: str = "openai/gpt-oss-120b:free",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    def _require_key(self) -> str:
        key = (self.api_key or "").strip()
        if not key:
            raise OpenRouterClientError("OPENROUTER_API_KEY is not configured. Create .env from .env.example.")
        return key

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.1,
        response_format: dict[str, Any] | None = None,
        timeout: float = 120,
    ) -> dict[str, Any]:
        api_key = self._require_key()
        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "LLM Data Analyst Lab",
        }
        url = f"{self.base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.RequestError as exc:
            raise OpenRouterClientError(f"OpenRouter request failed: {exc}") from exc

        text_preview = response.text[:500]
        if response.status_code == 401:
            raise OpenRouterClientError("OpenRouter authentication failed. Check OPENROUTER_API_KEY.")
        if response.status_code == 429:
            raise OpenRouterClientError("OpenRouter rate limit reached. Try again later.")
        if response.status_code == 503:
            raise OpenRouterClientError("OpenRouter is at capacity. Try again later.")
        if response.status_code >= 400:
            low = response.text.lower()
            if "model" in low and ("unavailable" in low or "not found" in low):
                raise OpenRouterClientError("OpenRouter model is unavailable. Check OPENROUTER_MODEL.")
            raise OpenRouterClientError(f"OpenRouter request failed with status {response.status_code}: {text_preview}")

        try:
            data = response.json()
        except ValueError as exc:
            raise OpenRouterClientError("OpenRouter returned non-JSON payload.") from exc

        return data

    @staticmethod
    def _extract_content(response_json: dict[str, Any]) -> str:
        choices = response_json.get("choices")
        if not isinstance(choices, list) or not choices:
            raise OpenRouterClientError("OpenRouter response does not contain choices.")
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    chunks.append(item["text"])
            if chunks:
                return "\n".join(chunks)
        raise OpenRouterClientError("OpenRouter response does not contain text content.")

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.1,
        timeout: float = 120,
    ) -> dict[str, Any]:
        response_json = await self.chat(messages=messages, model=model, temperature=temperature, timeout=timeout)
        content = self._extract_content(response_json).strip()

        fenced = re.search(r"```json\s*(.*?)\s*```", content, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            content = fenced.group(1).strip()

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    parsed = json.loads(content[start : end + 1])
                except json.JSONDecodeError as exc:
                    raise OpenRouterClientError(f"Invalid JSON from OpenRouter. Preview: {content[:400]}") from exc
            else:
                raise OpenRouterClientError(f"Invalid JSON from OpenRouter. Preview: {content[:400]}")

        if not isinstance(parsed, dict):
            raise OpenRouterClientError("OpenRouter JSON response must be an object.")

        return parsed
