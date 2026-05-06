from __future__ import annotations

import json
import re
from typing import Any, Awaitable, Callable


def sse_event(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


class StreamEmitter:
    def __init__(self, sender: Callable[[str], Awaitable[None]]) -> None:
        self._sender = sender

    async def emit(self, event_type: str, data: dict[str, Any]) -> None:
        await self._sender(sse_event(event_type, data))


def chunk_text_for_streaming(text: str) -> list[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    chunks = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n{2,}", cleaned) if part.strip()]
    if chunks:
        return [chunk + ("" if chunk.endswith((".", "!", "?")) else " ") for chunk in chunks]
    return [cleaned]
