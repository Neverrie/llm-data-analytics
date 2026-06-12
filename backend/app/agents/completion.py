from typing import Any

from app.llm.client import LlmClient


def needs_finalization(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    if len(normalized) < 8 or not any(char.isalnum() for char in normalized):
        return True
    transitional_markers = (
        "проверю итог",
        "проверим итог",
        "сейчас провер",
        "далее провер",
        "i will check",
        "let me check",
        "i'll verify",
    )
    return any(marker in normalized for marker in transitional_markers)


def is_usable_finalization(text: str) -> bool:
    normalized = (text or "").strip()
    return len(normalized) >= 8 and any(char.isalnum() for char in normalized) and not needs_finalization(normalized)


def finalize_user_answer(
    llm: LlmClient,
    messages: list[dict[str, Any]],
    draft: str,
    files: dict[str, dict[str, Any]],
    failure_note: str | None = None,
) -> str:
    filenames = sorted(
        {
            str(item.get("filename") or "")
            for item in files.values()
            if item.get("filename")
        }
    )
    requirement = (
        "Сформируй законченный финальный ответ пользователю на русском языке. "
        "Не обещай будущих действий. Используй фактические результаты выполненных инструментов. "
        "Рассматривай каждый пункт текущего запроса как чек-лист: приведи все явно запрошенные метрики, "
        "сравнения и выводы. Используй компактный Markdown и перечисли созданные файлы."
    )
    if filenames:
        requirement += f" Созданные файлы: {', '.join(filenames)}."
    if failure_note:
        requirement += f" Честно укажи ограничение: {failure_note}"

    final_messages = [
        *messages,
        {
            "role": "user",
            "content": (
                f"{requirement} "
                "Верни только готовый финальный ответ на основе результатов выше. "
                f"Предыдущий черновик был неполным: {draft}"
            ),
        },
    ]
    response = llm.chat(messages=final_messages, tools=None)
    return (response.content or "").strip()
