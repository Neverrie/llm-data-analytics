from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.config import get_lab3_model, settings
from app.services.lab2_service import Lab2PipelineError


def get_langchain_chat_model(model: str | None = None, temperature: float = 0) -> ChatOpenAI:
    api_key = (settings.openrouter_api_key or "").strip()
    if not api_key:
        raise Lab2PipelineError("OPENROUTER_API_KEY is not configured. Create .env from .env.example.", status_code=500)

    chosen_model = (model or get_lab3_model()).strip()
    if chosen_model == "qwen3:8b":
        raise Lab2PipelineError("Invalid OpenRouter model slug: qwen3:8b. Use OpenRouter model slugs only.", status_code=400)

    return ChatOpenAI(
        model=chosen_model,
        base_url=settings.openrouter_base_url,
        api_key=api_key,
        temperature=temperature,
        timeout=settings.openrouter_timeout_seconds,
    )
