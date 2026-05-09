from __future__ import annotations

import json
import logging
from typing import Any

from app.services.llm_client import LLMClient, LLMClientError

logger = logging.getLogger(__name__)


def _history_for_router(messages: list[dict[str, Any]], limit: int = 8) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in messages[-limit:]:
        role = str(item.get("role") or "user")
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        out.append({"role": role, "content": content[:1200]})
    return out


def _minimal_fallback_route(user_message: str) -> dict[str, str]:
    low = user_message.lower()
    asks_data = any(token in low for token in ["датасет", "таблиц", "график", "посч", "корреляц", "кластер", "pca"])
    if asks_data:
        return {
            "route": "analyze_with_code",
            "reason": "Явный запрос на анализ данных.",
            "user_intent": "выполнить анализ датасета",
        }
    return {
        "route": "answer_directly",
        "reason": "Безопасный fallback: явного запроса на вычисления нет.",
        "user_intent": "уточнение или диалог без запуска кода",
    }


async def route_dataset_chat(
    *,
    user_message: str,
    dataset_name: str,
    recent_messages: list[dict[str, Any]],
    conversation_context: dict[str, Any] | None = None,
    followup_intent: dict[str, Any] | None = None,
) -> dict[str, str]:
    conversation_context = conversation_context or {}
    followup_intent = followup_intent or {}
    intent_name = str(followup_intent.get("intent") or "")
    if intent_name in {"retry_previous_task", "continue_previous_task", "refine_previous_answer"}:
        last_req = str(conversation_context.get("last_user_analysis_request") or "").strip()
        if last_req:
            return {
                "route": "analyze_with_code",
                "reason": "Короткий follow-up запрос в контексте предыдущей аналитической задачи.",
                "user_intent": f"{intent_name}: {last_req[:120]}",
            }
    system_prompt = (
        "Ты router для чата аналитика данных.\n\n"
        "Всегда пиши поля reason и user_intent на русском языке. "
        "Исключение: технические идентификаторы, имена колонок и файлов.\n\n"
        "Твоя задача — решить, нужно ли запускать Python code interpreter.\n\n"
        "У пользователя может быть выбран датасет. Это значит, что датасет доступен как контекст, "
        "но это НЕ значит, что каждый вопрос требует кода.\n\n"
        "Запускай code interpreter только если пользователь просит выполнить анализ данных, вычисления, "
        "построить график, вывести строки датасета, проверить качество данных, сгруппировать, посчитать статистики, "
        "обучить модель, найти закономерности или создать файл/таблицу/визуализацию на основе данных.\n\n"
        "Также запускай code interpreter, если пользователь просит обзор датасета, описание колонок, "
        "первые строки, сводную статистику или оценку содержимого датасета.\n\n"
        "Не запускай code interpreter, если пользователь:\n"
        "- здоровается;\n"
        "- спрашивает о возможностях системы;\n"
        "- спрашивает, почему произошла ошибка;\n"
        "- обсуждает предыдущий ответ;\n"
        "- просит объяснить концепт;\n"
        "- просит уточнить, что произошло;\n"
        "- задаёт вопрос о Docker, sandbox, интерфейсе, промптах или работе агента;\n"
        "- ведёт обычный диалог, не требующий чтения/вычисления данных.\n\n"
        "Если вопрос можно ответить по истории чата, профилю датасета или предыдущим результатам без нового "
        "выполнения кода — не запускай code interpreter.\n\n"
        "Few-shot examples:\n"
        'Пользователь: "привет"\n'
        'Ответ: {"route":"answer_directly","reason":"Обычное приветствие, анализ данных не требуется.","user_intent":"поздороваться"}\n'
        'Пользователь: "почему у меня Docker binary not found?"\n'
        'Ответ: {"route":"answer_directly","reason":"Пользователь спрашивает о системной ошибке, запуск кода не нужен.","user_intent":"понять причину ошибки"}\n'
        'Пользователь: "выведи несколько строк из датасета"\n'
        'Ответ: {"route":"analyze_with_code","reason":"Нужно прочитать датасет и показать строки.","user_intent":"посмотреть первые строки датасета"}\n'
        'Пользователь: "что скажешь по датасету?"\n'
        'Ответ: {"route":"analyze_with_code","reason":"Нужен фактологический обзор по данным датасета.","user_intent":"получить обзор датасета"}\n'
        'Пользователь: "что значит корреляция?"\n'
        'Ответ: {"route":"answer_directly","reason":"Это концептуальное объяснение, вычисления не требуются.","user_intent":"понять термин"}\n'
        'Пользователь: "посчитай корреляцию между rating и price"\n'
        'Ответ: {"route":"analyze_with_code","reason":"Нужно выполнить вычисления по датасету.","user_intent":"посчитать корреляцию"}\n'
        'Пользователь: "а теперь объясни этот график"\n'
        'Ответ: {"route":"answer_directly","reason":"Можно ответить по предыдущему результату и истории чата без нового кода.","user_intent":"объяснить прошлый график"}\n\n'
        'Верни строго JSON без markdown: {"route":"answer_directly|analyze_with_code","reason":"...","user_intent":"..."}'
    )
    history_payload = _history_for_router(recent_messages)
    user_prompt = (
        f"dataset_name: {dataset_name}\n"
        f"history: {history_payload}\n"
        f"conversation_context: {json.dumps(conversation_context, ensure_ascii=False)}\n"
        f"followup_intent: {json.dumps(followup_intent, ensure_ascii=False)}\n"
        f"user_message: {user_message}"
    )
    client = LLMClient()
    try:
        raw = await client.chat_json(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            purpose="general",
            temperature=0,
        )
        route = str(raw.get("route") or "").strip()
        reason = str(raw.get("reason") or "").strip()
        intent = str(raw.get("user_intent") or "").strip()
        if route not in {"answer_directly", "analyze_with_code"}:
            raise ValueError("invalid route")
        return {
            "route": route,
            "reason": reason or "Маршрут выбран LLM-роутером.",
            "user_intent": intent or user_message[:80],
        }
    except (LLMClientError, ValueError, TypeError):
        logger.warning("CHAT_ROUTER_FALLBACK user_message=%s", user_message[:200])
        fallback = _minimal_fallback_route(user_message)
        fallback["reason"] = f"{fallback['reason']} (router fallback after parse/model failure)"
        return fallback
