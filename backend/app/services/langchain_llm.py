from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI

from app.config import get_lab3_model, settings


def get_langchain_chat_model(model: str | None = None, temperature: float = 0) -> Any:
    provider = (settings.llm_provider or "").strip().lower()
    chosen_model = (model or get_lab3_model()).strip()
    if provider == "gemini":
        api_key = (settings.gemini_api_key or "").strip()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured. Create .env from .env.example.")
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("langchain-google-genai is not installed in backend image.") from exc
        return ChatGoogleGenerativeAI(
            model=chosen_model or settings.gemini_model,
            google_api_key=api_key,
            temperature=temperature,
        )

    if provider == "openrouter":
        api_key = (settings.openrouter_api_key or "").strip()
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured. Create .env from .env.example.")
        if chosen_model == "qwen3:8b":
            raise RuntimeError("Invalid OpenRouter model slug: qwen3:8b. Use OpenRouter model slugs only.")
        return ChatOpenAI(
            model=chosen_model,
            base_url=settings.openrouter_base_url,
            api_key=api_key,
            temperature=temperature,
            timeout=settings.openrouter_timeout_seconds,
        )

    if provider == "ollama":
        return ChatOpenAI(
            model=chosen_model or settings.ollama_model,
            base_url=f"{settings.ollama_base_url.rstrip('/')}/v1",
            api_key="ollama",
            temperature=temperature,
            timeout=settings.openrouter_timeout_seconds,
        )

    raise RuntimeError(f"Unsupported LLM_PROVIDER={provider}. Supported providers: openrouter, gemini, ollama.")
