from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from app.config import get_default_model_for_provider, get_lab3_model, settings
from app.ollama_client import OllamaClient, OllamaClientError
from app.services.langchain_llm import get_langchain_chat_model
from app.services.openrouter_client import OpenRouterClient, OpenRouterClientError
from app.stream_events import chunk_text_for_streaming


class LLMClientError(RuntimeError):
    pass


class LLMClient:
    def __init__(self) -> None:
        self.provider = settings.llm_provider.lower().strip()

    def resolve_model(self, model: str | None = None, purpose: str | None = None) -> str:
        if model:
            return model
        if (purpose or "").strip().lower() in {"code_interpreter", "lab3", "planner", "final_answer", "critic"}:
            return get_lab3_model()
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

    @staticmethod
    def _gemini_retry_delay_seconds(message: str) -> int | None:
        low = message.lower()
        if "quota exceeded" not in low and "resourceexhausted" not in low and "429" not in low:
            return None
        match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", message, flags=re.IGNORECASE)
        if match:
            return max(1, int(float(match.group(1))))
        match = re.search(r"seconds:\s*([0-9]+)", message, flags=re.IGNORECASE)
        if match:
            return max(1, int(match.group(1)))
        return 25

    async def _gemini_ainvoke_with_retry(self, model: Any, messages: list[dict[str, str]]) -> Any:
        attempts = 0
        while True:
            attempts += 1
            try:
                return await model.ainvoke(messages)
            except Exception as exc:
                delay = self._gemini_retry_delay_seconds(str(exc))
                if delay is None or attempts >= 3:
                    raise
                await asyncio.sleep(min(delay + 1, 60))

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
                    return await client.chat_json(
                        messages=messages,
                        model=current_model,
                        temperature=temperature,
                        timeout=settings.openrouter_timeout_seconds,
                    )
                payload = await client.chat(
                    messages=messages,
                    model=current_model,
                    temperature=temperature,
                    timeout=settings.openrouter_timeout_seconds,
                )
                content = str(payload.get("content", "")).strip()
                if not content:
                    retry_messages = [*messages, {"role": "user", "content": "Return a concise non-empty answer."}]
                    retry_payload = await client.chat(
                        messages=retry_messages,
                        model=current_model,
                        temperature=temperature,
                        timeout=settings.openrouter_timeout_seconds,
                    )
                    content = str(retry_payload.get("content", "")).strip()
                if not content:
                    raise LLMClientError("Model returned empty content twice.")
                return content
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
        resolved_model = self.resolve_model(model, purpose)
        try:
            if self.provider == "openrouter":
                return await self._openrouter_chat_with_fallback(
                    messages=messages,
                    model=resolved_model,
                    temperature=temperature,
                    want_json=False,
                )
            if self.provider == "gemini":
                lc_model = get_langchain_chat_model(model=resolved_model, temperature=temperature)
                resp = await self._gemini_ainvoke_with_retry(lc_model, messages)
                content = getattr(resp, "content", "")
                if isinstance(content, str):
                    text = content.strip()
                elif isinstance(content, list):
                    text = "\n".join(
                        str(item.get("text", "")).strip() if isinstance(item, dict) else str(item).strip()
                        for item in content
                    ).strip()
                else:
                    text = str(content).strip()
                if not text:
                    raise LLMClientError("Gemini returned empty content.")
                return text

            prompt = "\n\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages)
            resp = await OllamaClient(settings.ollama_base_url).generate_text(resolved_model, prompt)
            return resp.response.strip()
        except (OpenRouterClientError, OllamaClientError, RuntimeError) as exc:
            raise LLMClientError(str(exc)) from exc

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        purpose: str = "json",
        model: str | None = None,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        resolved_model = self.resolve_model(model, purpose)
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
            if self.provider == "gemini":
                lc_model = get_langchain_chat_model(model=resolved_model, temperature=temperature)
                json_messages = [
                    *messages,
                    {
                        "role": "user",
                        "content": "Return strictly valid JSON object only. No markdown fences.",
                    },
                ]
                resp = await self._gemini_ainvoke_with_retry(lc_model, json_messages)
                content = getattr(resp, "content", "")
                text = content.strip() if isinstance(content, str) else str(content).strip()
                fenced = re.search(r"```json\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
                if fenced:
                    text = fenced.group(1).strip()
                parsed = json.loads(text)
                if not isinstance(parsed, dict):
                    raise LLMClientError("LLM JSON response must be an object.")
                return parsed

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
        except (OpenRouterClientError, OllamaClientError, json.JSONDecodeError, RuntimeError) as exc:
            raise LLMClientError(str(exc)) from exc

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        purpose: str = "general",
        model: str | None = None,
        temperature: float = 0.1,
    ):
        resolved_model = self.resolve_model(model, purpose)
        if self.provider == "openrouter":
            models = [resolved_model, *[m for m in self._fallback_models() if m != resolved_model]]
            last_error: Exception | None = None
            for index, current_model in enumerate(models):
                client = OpenRouterClient(
                    api_key=settings.openrouter_api_key,
                    base_url=settings.openrouter_base_url,
                    default_model=settings.openrouter_model,
                )
                try:
                    yielded = False
                    async for chunk in client.stream_chat_completion(
                        messages=messages,
                        model=current_model,
                        temperature=temperature,
                    ):
                        yielded = True
                        yield chunk
                    if yielded:
                        return
                except OpenRouterClientError as exc:
                    last_error = exc
                    if "authentication failed" in str(exc).lower():
                        raise LLMClientError(str(exc)) from exc
                    if index < len(models) - 1 and self._is_retryable_openrouter_error(str(exc)):
                        continue
                    break
            raise LLMClientError(str(last_error) if last_error else "OpenRouter stream failed.")
        if self.provider == "gemini":
            try:
                text = await self.chat(messages=messages, purpose=purpose, model=resolved_model, temperature=temperature)
                for chunk in chunk_text_for_streaming(text):
                    yield chunk
                return
            except (LLMClientError, RuntimeError) as exc:
                raise LLMClientError(str(exc)) from exc

        try:
            prompt = "\n\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages)
            resp = await OllamaClient(settings.ollama_base_url).generate_text(resolved_model, prompt)
            for chunk in chunk_text_for_streaming(resp.response):
                yield chunk
        except OllamaClientError as exc:
            raise LLMClientError(str(exc)) from exc
