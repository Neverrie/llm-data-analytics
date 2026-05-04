from __future__ import annotations

import json
import re
from typing import Any

from app.config import settings
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
        if self.provider == "openrouter":
            return settings.openrouter_model
        return settings.ollama_model

    def provider_name(self) -> str:
        return self.provider

    def is_configured(self) -> bool:
        if self.provider == "openrouter":
            return bool((settings.openrouter_api_key or "").strip())
        return True

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
                client = OpenRouterClient(
                    api_key=settings.openrouter_api_key,
                    base_url=settings.openrouter_base_url,
                    default_model=settings.openrouter_model,
                )
                payload = await client.chat(messages=messages, model=resolved_model, temperature=temperature)
                return OpenRouterClient._extract_content(payload).strip()

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
                client = OpenRouterClient(
                    api_key=settings.openrouter_api_key,
                    base_url=settings.openrouter_base_url,
                    default_model=settings.openrouter_model,
                )
                return await client.chat_json(messages=messages, model=resolved_model, temperature=temperature)

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
