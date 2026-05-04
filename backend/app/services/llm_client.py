from __future__ import annotations

import json
import re
from typing import Any

from app.config import get_default_model_for_provider, settings
from app.ollama_client import OllamaClient, OllamaClientError
from app.services.openrouter_client import OpenRouterClient, OpenRouterClientError


class LLMClientError(RuntimeError):
    pass


class LLMClient:
    def __init__(self) -> None:
        self.provider = settings.llm_provider.lower().strip()

    def resolve_model(self, model: str | None = None) -> str:
        if model:
            return model
        return get_default_model_for_provider(self.provider)

    def provider_name(self) -> str:
        return self.provider

    def is_configured(self) -> bool:
        if self.provider == "openrouter":
            return bool((settings.openrouter_api_key or "").strip())
        return True

    @staticmethod
    def _fallback_models() -> list[str]:
        raw = (settings.openrouter_fallback_models or "").strip()
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]

    @staticmethod
    def _is_retryable_openrouter_error(message: str) -> bool:
        low = message.lower()
        return any(token in low for token in ["rate limit", "capacity", "temporarily unavailable", "overloaded", "try again later"])

    async def _openrouter_chat_with_fallback(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        want_json: bool,
    ) -> Any:
        models = [model, *[m for m in self._fallback_models() if m != model]]
        client = OpenRouterClient(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            default_model=settings.openrouter_model,
        )
        last_error: Exception | None = None

        for index, current_model in enumerate(models):
            try:
                if want_json:
                    return await client.chat_json(messages=messages, model=current_model, temperature=temperature)
                payload = await client.chat(messages=messages, model=current_model, temperature=temperature)
                return str(payload.get("content", "")).strip()
            except OpenRouterClientError as exc:
                last_error = exc
                if "authentication failed" in str(exc).lower():
                    raise LLMClientError(str(exc)) from exc
                if index < len(models) - 1 and self._is_retryable_openrouter_error(str(exc)):
                    continue
                raise LLMClientError(str(exc)) from exc

        raise LLMClientError(str(last_error) if last_error else "OpenRouter request failed.")

    async def chat(
        self,
        messages: list[dict[str, str]],
        purpose: str = "general",
        model: str | None = None,
        temperature: float = 0.1,
    ) -> str:
        resolved_model = self.resolve_model(model)
        try:
            if self.provider == "openrouter":
                return await self._openrouter_chat_with_fallback(
                    messages=messages,
                    model=resolved_model,
                    temperature=temperature,
                    want_json=False,
                )

            prompt = "\n\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages)
            resp = await OllamaClient(settings.ollama_base_url).generate_text(resolved_model, prompt)
            return resp.response.strip()
        except (OpenRouterClientError, OllamaClientError) as exc:
            raise LLMClientError(str(exc)) from exc

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        purpose: str = "json",
        model: str | None = None,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        resolved_model = self.resolve_model(model)
        try:
            if self.provider == "openrouter":
                result = await self._openrouter_chat_with_fallback(
                    messages=messages,
                    model=resolved_model,
                    temperature=temperature,
                    want_json=True,
                )
                if not isinstance(result, dict):
                    raise LLMClientError("LLM JSON response must be an object.")
                return result

            prompt = "\n\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages)
            resp = await OllamaClient(settings.ollama_base_url).generate_json(resolved_model, prompt)
            text = resp.response.strip()
            fenced = re.search(r"```json\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
            if fenced:
                text = fenced.group(1).strip()
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                raise LLMClientError("LLM JSON response must be an object.")
            return parsed
        except (OpenRouterClientError, OllamaClientError, json.JSONDecodeError) as exc:
            raise LLMClientError(str(exc)) from exc
