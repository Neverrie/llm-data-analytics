from __future__ import annotations

import json

import pytest
import httpx

from app.services.openrouter_client import OpenRouterClient, OpenRouterClientError


@pytest.mark.asyncio
async def test_openrouter_client_missing_key() -> None:
    client = OpenRouterClient(api_key=None)
    with pytest.raises(OpenRouterClientError) as exc:
        await client.chat(messages=[{"role": "user", "content": "hello"}])
    assert "OPENROUTER_API_KEY is not configured" in str(exc.value)


def test_extract_openrouter_text_string_content() -> None:
    payload = {"choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}], "model": "m"}
    assert OpenRouterClient.extract_openrouter_text(payload) == "hello"


def test_extract_openrouter_text_list_content() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "text", "text": "first"},
                        {"type": "output_text", "text": "second"},
                    ]
                }
            }
        ],
        "model": "m",
    }
    text = OpenRouterClient.extract_openrouter_text(payload)
    assert "first" in text and "second" in text


def test_extract_openrouter_text_reasoning_fallback() -> None:
    payload = {"choices": [{"message": {"content": "", "reasoning": "reason text"}}], "model": "m"}
    assert OpenRouterClient.extract_openrouter_text(payload) == "reason text"


def test_extract_openrouter_text_missing_content_preview() -> None:
    payload = {"choices": [{"message": {}, "finish_reason": "stop"}], "model": "m"}
    with pytest.raises(OpenRouterClientError) as exc:
        OpenRouterClient.extract_openrouter_text(payload)
    assert "did not contain usable text" in str(exc.value)
    assert "Preview:" in str(exc.value)


def test_extract_openrouter_text_tool_calls_error() -> None:
    payload = {"choices": [{"message": {"tool_calls": [{"id": "1"}]}}], "model": "m"}
    with pytest.raises(OpenRouterClientError) as exc:
        OpenRouterClient.extract_openrouter_text(payload)
    assert "tool_calls" in str(exc.value)


@pytest.mark.asyncio
async def test_openrouter_chat_returns_raw_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenRouterClient(api_key="x")

    class FakeResponse:
        status_code = 200
        text = "ok"

        def json(self):
            return {"choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}], "model": "m"}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    import app.services.openrouter_client as module

    monkeypatch.setattr(module.httpx, "AsyncClient", FakeAsyncClient)

    result = await client.chat(messages=[{"role": "user", "content": "hi"}])
    assert result["content"] == "hello"
    assert result["provider"] == "openrouter"
    assert "raw_preview" in result and isinstance(result["raw_preview"], dict)


@pytest.mark.asyncio
async def test_openrouter_timeout_message(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenRouterClient(api_key="x")

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            raise httpx.TimeoutException("timeout")

    import app.services.openrouter_client as module

    monkeypatch.setattr(module.httpx, "AsyncClient", FakeAsyncClient)
    with pytest.raises(OpenRouterClientError) as exc:
        await client.chat(messages=[{"role": "user", "content": "hi"}], timeout=60)
    assert "timed out after 60 seconds" in str(exc.value)
