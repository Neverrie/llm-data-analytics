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

    @staticmethod
    def make_openrouter_response_preview(response_json: dict[str, Any]) -> dict[str, Any]:
        choices = response_json.get("choices")
        choice0 = choices[0] if isinstance(choices, list) and choices else {}
        if not isinstance(choice0, dict):
            choice0 = {}
        message = choice0.get("message")
        if not isinstance(message, dict):
            message = {}

        content = message.get("content")
        content_type = "none"
        content_preview: str | None = None
        if isinstance(content, str):
            content_type = "str"
            content_preview = content[:300]
        elif isinstance(content, list):
            content_type = "list"
            content_preview = json.dumps(content[:2], ensure_ascii=False)[:300]

        return {
            "top_level_keys": list(response_json.keys()),
            "choice_keys": list(choice0.keys()),
            "message_keys": list(message.keys()),
            "finish_reason": choice0.get("finish_reason"),
            "model": response_json.get("model"),
            "content_type": content_type,
            "content_preview": content_preview,
        }

    @staticmethod
    def _extract_text_from_parts(parts: list[Any]) -> str:
        chunks: list[str] = []
        for item in parts:
            if isinstance(item, str) and item.strip():
                chunks.append(item)
                continue
            if not isinstance(item, dict):
                continue
            for key in ("text", "content", "output_text", "value"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    chunks.append(value)
                    break
        return "\n".join(chunks).strip()

    @classmethod
    def extract_openrouter_text(cls, response_json: dict[str, Any]) -> str:
        choices = response_json.get("choices")
        if not isinstance(choices, list) or not choices:
            raise OpenRouterClientError("OpenRouter response does not contain choices.")

        choice0 = choices[0]
        if not isinstance(choice0, dict):
            raise OpenRouterClientError("OpenRouter response choice is not an object.")

        message = choice0.get("message") if isinstance(choice0.get("message"), dict) else {}

        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            extracted = cls._extract_text_from_parts(content)
            if extracted:
                return extracted

        for key in ("reasoning", "reasoning_content"):
            value = message.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, list):
                extracted = cls._extract_text_from_parts(value)
                if extracted:
                    return extracted

        for source in (choice0, response_json):
            reasoning = source.get("reasoning") if isinstance(source, dict) else None
            if isinstance(reasoning, str) and reasoning.strip():
                return reasoning.strip()
            if isinstance(reasoning, list):
                extracted = cls._extract_text_from_parts(reasoning)
                if extracted:
                    return extracted

        if message.get("tool_calls") or message.get("function_call"):
            raise OpenRouterClientError("OpenRouter returned tool_calls instead of text content.")

        preview = cls.make_openrouter_response_preview(response_json)
        raise OpenRouterClientError(f"OpenRouter response did not contain usable text. Preview: {json.dumps(preview, ensure_ascii=False)}")

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.1,
        response_format: dict[str, Any] | None = None,
        timeout: float = 120,
    ) -> dict[str, Any]:
        api_key = self._require_key()
        used_model = model or self.default_model
        payload: dict[str, Any] = {
            "model": used_model,
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
            response_json = response.json()
        except ValueError as exc:
            raise OpenRouterClientError("OpenRouter returned non-JSON payload.") from exc

        content = self.extract_openrouter_text(response_json)
        preview = self.make_openrouter_response_preview(response_json)
        return {
            "content": content,
            "model": used_model,
            "provider": "openrouter",
            "attempts": [{"model": used_model, "status": "ok"}],
            "raw_preview": preview,
            "raw": response_json,
        }

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.1,
        timeout: float = 120,
    ) -> dict[str, Any]:
        response_payload = await self.chat(messages=messages, model=model, temperature=temperature, timeout=timeout)
        content = str(response_payload.get("content", "")).strip()

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
