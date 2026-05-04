from __future__ import annotations

import pytest

from app.config import settings
from app.services.langchain_llm import get_langchain_chat_model


def test_langchain_llm_uses_openrouter_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "openrouter_base_url", "https://openrouter.ai/api/v1")
    monkeypatch.setattr(settings, "openrouter_model", "openai/gpt-oss-120b:free")
    model = get_langchain_chat_model()
    assert "openrouter.ai/api/v1" in str(model.openai_api_base)


def test_langchain_openrouter_model_slug_not_qwen3(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    with pytest.raises(Exception):
        get_langchain_chat_model(model="qwen3:8b")
