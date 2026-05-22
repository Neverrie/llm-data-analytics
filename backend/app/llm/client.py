import json
from typing import Any

import httpx

from app.config import settings
from app.llm.models import LlmMessage, LlmResponse, LlmToolCall


class LlmClientError(RuntimeError):
    pass


class LlmClient:
    def __init__(self, timeout_seconds: int = 120):
        self.timeout_seconds = timeout_seconds

    def _build_url(self) -> str:
        base = settings.openrouter_base_url.rstrip("/")
        return f"{base}/chat/completions"

    def chat(self, messages: list[LlmMessage | dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LlmResponse:
        if (settings.llm_provider or "").lower() != "openrouter":
            raise LlmClientError(f"Unsupported llm_provider: {settings.llm_provider}")
        if not settings.openrouter_api_key:
            raise LlmClientError("OPENROUTER_API_KEY is not set")
        if not settings.openrouter_model:
            raise LlmClientError("OPENROUTER_MODEL is not set")

        normalized_messages: list[dict[str, Any]] = []
        for msg in messages:
            if isinstance(msg, LlmMessage):
                payload = msg.model_dump(exclude_none=True)
            else:
                payload = {k: v for k, v in dict(msg).items() if v is not None}
            normalized_messages.append(payload)

        payload: dict[str, Any] = {
            "model": settings.openrouter_model,
            "messages": normalized_messages,
        }

        if tools:
            norm_tools: list[dict[str, Any]] = []
            for t in tools:
                if "function" in t and isinstance(t.get("function"), dict):
                    norm_tools.append({"type": "function", "function": t["function"]})
                    continue
                fn = dict(t)
                if "input_schema" in fn and "parameters" not in fn:
                    fn["parameters"] = fn.pop("input_schema")
                norm_tools.append({"type": "function", "function": fn})
            payload["tools"] = norm_tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(self._build_url(), headers=headers, json=payload)
        except Exception as exc:
            raise LlmClientError(f"OpenRouter request failed: {exc}") from exc

        if response.status_code >= 400:
            raise LlmClientError(f"OpenRouter HTTP {response.status_code}: {response.text[:1000]}")

        try:
            data = response.json()
        except Exception as exc:
            raise LlmClientError("OpenRouter response is not JSON") from exc

        choices = data.get("choices") or []
        if not choices:
            raise LlmClientError("OpenRouter response has no choices")

        message = choices[0].get("message") or {}
        content = str(message.get("content") or "")

        tool_calls: list[LlmToolCall] = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function") or {}
            fn_name = str(fn.get("name") or "").strip()
            raw_args = fn.get("arguments")
            parsed_args: dict[str, Any] = {}
            if isinstance(raw_args, dict):
                parsed_args = raw_args
            elif isinstance(raw_args, str) and raw_args.strip():
                try:
                    parsed = json.loads(raw_args)
                    if isinstance(parsed, dict):
                        parsed_args = parsed
                except Exception:
                    parsed_args = {"_raw": raw_args}
            if fn_name:
                tool_calls.append(LlmToolCall(id=tc.get("id"), name=fn_name, arguments=parsed_args))

        return LlmResponse(content=content, tool_calls=tool_calls, raw=data)
