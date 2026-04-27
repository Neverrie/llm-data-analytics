from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.lab2_service import Lab2PipelineError

MAX_SESSION_TURNS = 10


def _sessions_dir() -> Path:
    path = Path(settings.outputs_dir) / "lab3" / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _session_path(session_id: str) -> Path:
    safe = "".join(ch for ch in session_id if ch.isalnum() or ch in {"-", "_"})
    if not safe:
        raise Lab2PipelineError("Invalid session_id.", status_code=400)
    return _sessions_dir() / f"{safe}.json"


def create_session_id() -> str:
    return uuid.uuid4().hex


def load_session(session_id: str) -> dict[str, Any] | None:
    path = _session_path(session_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_session(session_id: str, state: dict[str, Any]) -> None:
    path = _session_path(session_id)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def reset_session(session_id: str) -> None:
    state = load_session(session_id)
    if state is None:
        raise Lab2PipelineError("Session not found.", status_code=404)
    state["turns"] = []
    state["conversation_summary"] = ""
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_session(session_id, state)


def _new_state(session_id: str, dataset_name: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "session_id": session_id,
        "dataset_name": dataset_name,
        "created_at": now,
        "updated_at": now,
        "turns": [],
        "conversation_summary": "",
    }


def _build_conversation_summary(turns: list[dict[str, Any]]) -> str:
    if not turns:
        return ""
    lines = []
    for idx, turn in enumerate(turns[-5:], start=1):
        question = str(turn.get("question", "")).strip()
        answer = str(turn.get("answer_summary", "")).strip()
        lines.append(f"{idx}. Вопрос: {question} | Краткий ответ: {answer}")
    return "\n".join(lines)


def append_turn(
    session_id: str,
    user_question: str,
    agent_answer: str,
    tool_summary: list[str],
    column_mapping: dict[str, Any],
    dataset_name: str,
    key_findings: list[str] | None = None,
) -> dict[str, Any]:
    state = load_session(session_id) or _new_state(session_id, dataset_name)
    if state.get("dataset_name") != dataset_name:
        state = _new_state(session_id, dataset_name)

    compact_answer = " ".join(agent_answer.strip().split())
    answer_summary = compact_answer[:320] + ("..." if len(compact_answer) > 320 else "")
    turn = {
        "question": user_question.strip(),
        "answer_summary": answer_summary,
        "tools_used": tool_summary[:20],
        "key_findings": (key_findings or [])[:8],
        "column_mapping_snapshot": column_mapping.get("roles", {}),
    }
    turns = list(state.get("turns", []))
    turns.append(turn)
    state["turns"] = turns[-MAX_SESSION_TURNS:]
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    state["conversation_summary"] = _build_conversation_summary(state["turns"])
    save_session(session_id, state)
    return state


def build_context_for_followup(session_id: str, dataset_name: str) -> dict[str, Any]:
    state = load_session(session_id)
    if state is None:
        return {"history_length": 0, "conversation_summary": "", "turns": []}
    if state.get("dataset_name") != dataset_name:
        return {
            "history_length": 0,
            "conversation_summary": "",
            "turns": [],
            "warning": "Session dataset differs from current dataset. History ignored.",
        }
    turns = list(state.get("turns", []))
    return {
        "history_length": len(turns),
        "conversation_summary": str(state.get("conversation_summary", "")),
        "turns": turns[-5:],
    }
