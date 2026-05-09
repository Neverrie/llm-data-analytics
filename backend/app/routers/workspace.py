import logging
import json
import base64
import re
import subprocess
import traceback
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote
import pandas as pd

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.schemas import (
    ChatDetailResponse,
    ChatItem,
    ChatMessageCreateRequest,
    ChatMessageItem,
    ChatsResponse,
    CreateChatRequest,
    UpdateChatRequest,
    UserPublic,
    WorkspaceCounts,
    WorkspaceResponse,
)
from app.services.artifact_service import artifact_to_message_block, register_artifact
from app.services.chat_router import route_dataset_chat
from app.services.auth_service import get_current_user, user_public
from app.services.code_sandbox import execute_python_code_general
from app.services.dataset_resolver import resolve_dataset_for_user
from app.services.lab3_service import ask_agent
from app.services.agent_runs import create_run, cancel_run, get_container_names
from app.services.llm_client import LLMClient, LLMClientError
from app.services.markdown_utils import normalize_markdown_tables, sanitize_model_final_answer
from app.services.workspace_service import (
    add_message,
    archive_chat,
    create_chat,
    get_chat,
    get_message_by_client_id,
    list_chats,
    update_chat,
    workspace_overview,
)
from app.db import fetch_all, get_connection
from app.stream_events import chunk_text_for_streaming, sse_event
from app.config import settings

router = APIRouter(tags=["workspace"])
logger = logging.getLogger(__name__)


def _sanitize_error_text(text: str) -> str:
    out = str(text or "")
    for raw in [
        getattr(settings, "openrouter_api_key", None),
        getattr(settings, "gemini_api_key", None),
        getattr(settings, "dashscope_api_key", None),
    ]:
        value = str(raw or "").strip()
        if value:
            out = out.replace(value, "***")
    out = re.sub(r"sk-[A-Za-z0-9_\-]+", "sk-***", out)
    return out


def _extract_python_block(text: str) -> str | None:
    src = str(text or "")
    tagged = re.search(r"<PYTHON>\s*(.*?)\s*</PYTHON>", src, flags=re.IGNORECASE | re.DOTALL)
    if tagged and tagged.group(1).strip():
        return tagged.group(1).strip()
    fenced = re.search(r"```(?:python|py)\s*(.*?)\s*```", src, flags=re.IGNORECASE | re.DOTALL)
    if fenced and fenced.group(1).strip():
        return fenced.group(1).strip()
    return None


def _extract_final_block(text: str) -> str | None:
    src = str(text or "")
    tagged = re.search(r"<FINAL>\s*(.*?)\s*</FINAL>", src, flags=re.IGNORECASE | re.DOTALL)
    if tagged and tagged.group(1).strip():
        return tagged.group(1).strip()
    return None


def _maybe_wants_code(user_text: str) -> bool:
    low = str(user_text or "").lower()
    return bool(
        re.search(r"\b(plot|chart|graph|python|code|script|график|построй|нарисуй|вычисли|посчитай|код)\b", low)
        or "```" in low
    )


def _table_block_from_file(path: str) -> dict | None:
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return None
    low = file_path.name.lower()
    try:
        if low.endswith(".json"):
            raw = json.loads(file_path.read_text(encoding="utf-8"))
            if isinstance(raw, list) and raw and isinstance(raw[0], dict):
                columns = list(raw[0].keys())
                rows = raw[:30]
                return {"type": "table", "title": file_path.name, "columns": columns, "rows": rows}
            if isinstance(raw, dict) and isinstance(raw.get("rows"), list) and isinstance(raw.get("columns"), list):
                return {"type": "table", "title": file_path.name, "columns": raw["columns"][:100], "rows": raw["rows"][:30]}
            return None
        if low.endswith(".csv"):
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if len(lines) < 2:
                return None
            header = [h.strip() for h in lines[0].split(",")]
            rows: list[dict] = []
            for line in lines[1:31]:
                values = [v.strip() for v in line.split(",")]
                row = {header[idx]: (values[idx] if idx < len(values) else "") for idx in range(len(header))}
                rows.append(row)
            return {"type": "table", "title": file_path.name, "columns": header, "rows": rows}
    except Exception:
        return None
    return None


def _image_data_url(path: str) -> str | None:
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return None
    ext = file_path.suffix.lower()
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(ext)
    if not mime:
        return None
    try:
        payload = base64.b64encode(file_path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{payload}"
    except Exception:
        return None


def _artifact_kind_by_name(name: str) -> str:
    low = name.lower()
    if re.search(r"\.(png|jpg|jpeg|webp)$", low):
        return "chart"
    if low.endswith(".md"):
        return "report"
    if low.endswith(".json"):
        return "json"
    if low.endswith(".csv"):
        return "table"
    return "other"


def _normalize_file_path_key(path: str) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    try:
        return str(Path(raw).resolve())
    except Exception:
        return raw.replace("\\", "/")


def _file_dedupe_key(file_item: dict[str, Any]) -> str:
    path = _normalize_file_path_key(str(file_item.get("path") or ""))
    if path:
        return f"path:{path}"
    name = str(file_item.get("name") or file_item.get("filename") or "").strip().lower()
    size = str(file_item.get("size") or file_item.get("size_bytes") or "")
    mime = str(file_item.get("mime_type") or "").strip().lower()
    return f"meta:{name}|{size}|{mime}"


def _artifact_dedupe_key(artifact: dict[str, Any]) -> str:
    path = _normalize_file_path_key(str(artifact.get("path") or ""))
    if path:
        return f"path:{path}"
    filename = str(artifact.get("filename") or "").strip().lower()
    size = str(artifact.get("size_bytes") or "")
    mime = str(artifact.get("mime_type") or "").strip().lower()
    if filename or size or mime:
        return f"meta:{filename}|{size}|{mime}"
    artifact_id = str(artifact.get("id") or "").strip()
    if artifact_id:
        return f"id:{artifact_id}"
    return "unknown"


def _chart_block_dedupe_key(block: dict[str, Any]) -> str:
    title = str(block.get("title") or block.get("filename") or "").strip().lower()
    mime = str(block.get("mime_type") or "").strip().lower()
    preview_url = str(block.get("preview_url") or block.get("url") or "").strip()
    if title or mime:
        return f"meta:{title}|{mime}"
    if preview_url:
        return f"url:{preview_url}"
    artifact_id = str(block.get("artifact_id") or "").strip()
    if artifact_id:
        return f"id:{artifact_id}"
    return "unknown"


def _artifact_to_block(artifact: dict) -> dict:
    mime = str(artifact.get("mime_type") or "")
    if mime.startswith("image/"):
        return {
            "type": "chart",
            "artifact_id": artifact.get("id"),
            "title": artifact.get("title"),
            "url": artifact.get("preview_url"),
            "preview_url": artifact.get("preview_url"),
            "download_url": artifact.get("download_url"),
            "mime_type": mime,
        }
    return {
        "type": "file",
        "artifact_id": artifact.get("id"),
        "title": artifact.get("title"),
        "filename": artifact.get("filename"),
        "download_url": artifact.get("download_url"),
        "preview_url": artifact.get("preview_url"),
        "mime_type": mime,
    }


def _is_dataset_overview_request(question: str) -> bool:
    low = (question or "").lower().strip()
    if not low:
        return False
    patterns = [
        r"\bhead\b",
        r"\bdf\.head\b",
        r"\bpreview\b",
        r"\bfirst\s*\d*\s*rows?\b",
        r"первые\s+\d+\s+строк",
        r"первые\s+строки",
        r"выведи\s+первые",
        r"выведи\s+строк",
        r"что\s+скажешь\s+по\s+датасет",
        r"обзор\s+датасет",
    ]
    return any(re.search(pattern, low) for pattern in patterns)


def _build_dataset_agent_context(user_id: str, chat_id: str, limit: int = 10) -> dict:
    chat_state = get_chat(user_id, chat_id)
    messages = chat_state.get("messages", [])
    recent_messages = [
        {
            "role": str(m.get("role") or ""),
            "content": str(m.get("content") or ""),
            "created_at": str(m.get("created_at") or ""),
        }
        for m in messages[-limit:]
    ]
    last_user_analysis_request = ""
    for msg in reversed(messages):
        if str(msg.get("role")) == "user":
            content = str(msg.get("content") or "").strip()
            if content and not re.search(r"^(попробуй еще раз|ещ[её] раз|retry|продолжи|а теперь)\s*$", content, flags=re.IGNORECASE):
                last_user_analysis_request = content
                break
    last_assistant_summary = ""
    last_successful_run: dict[str, Any] | None = None
    last_error: dict[str, Any] | None = None
    for msg in reversed(messages):
        if str(msg.get("role")) != "assistant":
            continue
        metadata = msg.get("metadata") if isinstance(msg.get("metadata"), dict) else {}
        blocks = msg.get("blocks") if isinstance(msg.get("blocks"), list) else []
        if not last_assistant_summary:
            last_assistant_summary = str(msg.get("content") or "")[:1400]
        if not last_error:
            warning = next((b for b in blocks if isinstance(b, dict) and b.get("type") == "warning"), None)
            if warning or metadata.get("error"):
                last_error = {
                    "content": str((warning or {}).get("content") or msg.get("content") or "")[:1200],
                    "error_type": str((warning or {}).get("error_type") or metadata.get("error_type") or ""),
                    "error_message": str(metadata.get("error_message") or "")[:1200],
                    "stderr": str(metadata.get("stderr") or "")[:1200],
                }
        if not last_successful_run and not metadata.get("error"):
            steps = metadata.get("code_steps") if isinstance(metadata.get("code_steps"), list) else []
            successful_execs = int(metadata.get("successful_executions_count") or 0)
            if steps or successful_execs > 0 or any(isinstance(b, dict) and b.get("type") in {"chart", "table", "execution"} for b in blocks):
                last_successful_run = {
                    "run_id": str(metadata.get("run_id") or ""),
                    "final_answer": str(msg.get("content") or "")[:1200],
                    "steps_count": len(steps),
                    "successful_executions_count": successful_execs,
                    "files": metadata.get("generated_files") if isinstance(metadata.get("generated_files"), list) else [],
                    "block_types": [str(b.get("type")) for b in blocks if isinstance(b, dict)],
                }
        if last_error and last_successful_run:
            break

    with get_connection() as conn:
        artifacts = fetch_all(
            conn,
            "SELECT filename, kind, mime_type FROM artifacts WHERE user_id = ? AND chat_id = ? ORDER BY created_at DESC LIMIT 30",
            (user_id, chat_id),
        )
    return {
        "recent_messages": recent_messages,
        "last_user_analysis_request": last_user_analysis_request,
        "last_assistant_summary": last_assistant_summary,
        "last_successful_run": last_successful_run,
        "last_error": last_error,
        "available_artifacts": artifacts,
    }


def _resolve_followup_intent(current_message: str, conversation_context: dict[str, Any]) -> dict[str, Any]:
    text = str(current_message or "").strip()
    low = text.lower()
    last_req = str(conversation_context.get("last_user_analysis_request") or "").strip()
    last_err = conversation_context.get("last_error") if isinstance(conversation_context.get("last_error"), dict) else {}
    new_task_patterns = [
        r"проанализируй\s+датасет",
        r"что\s+скажешь\s+по\s+датасету",
        r"сделай\s+обзор\s+датасета",
        r"покажи\s+структуру\s+датасета",
        r"\beda\b",
        r"найди\s+закономерности",
    ]
    if any(re.search(pattern, low) for pattern in new_task_patterns):
        return {"intent": "new_task", "resolved_task": text, "should_reference_previous_run": False}
    if re.search(r"^(попробуй еще раз|ещ[её] раз|retry|исправь|переделай)\s*$", low):
        resolved = f"Повтори предыдущую задачу: {last_req}" if last_req else text
        err_short = str(last_err.get("error_message") or last_err.get("content") or "").strip()
        if err_short:
            resolved = f"{resolved}. Исправь ошибку предыдущего запуска: {err_short[:500]}"
        return {"intent": "retry_previous_task", "resolved_task": resolved, "should_reference_previous_run": bool(last_req)}
    if re.search(r"^(продолжи|дальше|а теперь|теперь)\b", low):
        resolved = f"Продолжи предыдущую задачу: {last_req}. Уточнение: {text}" if last_req else text
        return {"intent": "continue_previous_task", "resolved_task": resolved, "should_reference_previous_run": True}
    if re.search(r"(подробнее|детальнее|раскрой|объясни подробнее)", low):
        resolved = f"Сделай подробнее предыдущий результат: {last_req}" if last_req else text
        return {"intent": "refine_previous_answer", "resolved_task": resolved, "should_reference_previous_run": True}
    return {"intent": "new_task", "resolved_task": text, "should_reference_previous_run": False}

def _build_dataset_overview_blocks(dataset_name: str, user_id: str | None) -> list[dict]:
    dataset_path = resolve_dataset_for_user(dataset_name, user_id).path
    if not dataset_path.exists() or not dataset_path.is_file():
        return []
    frame = pd.read_csv(dataset_path) if dataset_path.suffix.lower() == ".csv" else pd.read_excel(dataset_path)
    blocks: list[dict] = []
    head_df = frame.head(20)
    blocks.append(
        {
            "type": "table",
            "title": "Первые строки датасета",
            "columns": list(head_df.columns),
            "rows": head_df.to_dict(orient="records"),
        }
    )
    profile_rows = [{"column": col, "dtype": str(frame[col].dtype), "missing": int(frame[col].isna().sum())} for col in frame.columns]
    blocks.append(
        {
            "type": "table",
            "title": "Колонки и типы",
            "columns": ["column", "dtype", "missing"],
            "rows": profile_rows[:200],
        }
    )
    missing_df = frame.isna().sum().reset_index()
    missing_df.columns = ["column", "missing_count"]
    missing_df = missing_df[missing_df["missing_count"] > 0]
    if not missing_df.empty:
        blocks.append(
            {
                "type": "table",
                "title": "Пропуски",
                "columns": ["column", "missing_count"],
                "rows": missing_df.to_dict(orient="records")[:200],
            }
        )
    return blocks


async def _answer_directly_for_dataset_chat(
    *,
    question: str,
    dataset_name: str,
    recent_messages: list[dict],
) -> str:
    llm = LLMClient()
    messages = [
        {
            "role": "system",
            "content": (
                "Ты ассистент аналитики данных. Всегда отвечай пользователю на русском языке. "
                "Исключение: имена колонок, названия файлов, код, stdout/stderr и технические идентификаторы. "
                "Если вопрос про Docker/sandbox/backend ошибку, дай технически точное объяснение."
            ),
        },
        {
            "role": "system",
            "content": (
                f"Текущий датасет: {dataset_name}. "
                "Если вопрос не требует вычислений, отвечай без запуска code interpreter."
            ),
        },
        *[
            {"role": str(m.get("role") or "user"), "content": str(m.get("content") or "")}
            for m in recent_messages[-20:]
            if str(m.get("content") or "").strip()
        ],
        {"role": "user", "content": question},
    ]
    return await llm.chat(messages=messages, purpose="general", temperature=0.1)


@router.get("/workspace", response_model=WorkspaceResponse)
def get_workspace(user: dict = Depends(get_current_user)) -> WorkspaceResponse:
    data = workspace_overview(user["id"])
    return WorkspaceResponse(
        user=UserPublic.model_validate(user_public(user)),
        counts=WorkspaceCounts.model_validate(data["counts"]),
        recent_chats=[ChatItem.model_validate(item) for item in data["recent_chats"]],
        recent_artifacts=data["recent_artifacts"],
    )


@router.get("/chats", response_model=ChatsResponse)
def get_chats(
    kind: str | None = Query(default=None),
    archived: bool | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> ChatsResponse:
    items = list_chats(user["id"], kind=kind, archived=archived)
    return ChatsResponse(items=[ChatItem.model_validate(item) for item in items])


@router.post("/chats", response_model=ChatItem)
def post_chat(payload: CreateChatRequest, user: dict = Depends(get_current_user)) -> ChatItem:
    chat = create_chat(user["id"], payload.title, payload.kind, payload.dataset_name)
    chat["archived"] = bool(chat["archived"])
    return ChatItem.model_validate(chat)


@router.get("/chats/{chat_id}", response_model=ChatDetailResponse)
def get_chat_detail(chat_id: str, user: dict = Depends(get_current_user)) -> ChatDetailResponse:
    try:
        data = get_chat(user["id"], chat_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ChatDetailResponse(
        chat=ChatItem.model_validate(data["chat"]),
        messages=[ChatMessageItem.model_validate(item) for item in data["messages"]],
    )


@router.post("/chats/{chat_id}/messages", response_model=ChatMessageItem)
def post_chat_message(chat_id: str, payload: ChatMessageCreateRequest, user: dict = Depends(get_current_user)) -> ChatMessageItem:
    try:
        item = add_message(
            user["id"],
            chat_id,
            payload.role,
            payload.content,
            payload.blocks,
            payload.metadata,
            client_message_id=payload.client_message_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ChatMessageItem.model_validate(item)


@router.post("/chats/{chat_id}/messages/stream")
async def post_chat_message_stream(chat_id: str, payload: ChatMessageCreateRequest, user: dict = Depends(get_current_user)):
    async def event_generator():
        assistant_saved_id: str | None = None
        try:
            try:
                _ = get_chat(user["id"], chat_id)
            except ValueError as exc:
                yield sse_event("error", {"message": str(exc)})
                yield sse_event("done", {"status": "error"})
                return

            _ = add_message(
                user["id"],
                chat_id,
                payload.role,
                payload.content,
                payload.blocks,
                payload.metadata,
                client_message_id=payload.client_message_id,
            )

            yield sse_event("message_start", {"chat_id": chat_id, "role": "assistant"})
            yield sse_event("tool_start", {"name": "chat_generation"})
            yield sse_event("tool_log", {"content": "Request received. Preparing response..."})

            if payload.role.strip().lower() != "user":
                final_text = "Message saved."
                assistant_message = add_message(
                    user["id"],
                    chat_id,
                    "assistant",
                    final_text,
                    [{"type": "markdown", "content": final_text}],
                    {"stream_note": "non_user_role"},
                )
                assistant_saved_id = assistant_message["id"]
                yield sse_event("message_delta", {"content": final_text})
            else:
                chat_state = get_chat(user["id"], chat_id)
                dataset_name = chat_state.get("chat", {}).get("dataset_name")
                recent_messages = chat_state.get("messages", [])[-20:]
                user_text = str(payload.content or "")
                llm = LLMClient()
                wants_code = _maybe_wants_code(user_text)
                no_code_requested = bool(re.search(r"\b(не код|без кода|only graph|только график)\b", user_text.lower()))
                assistant_blocks: list[dict] = []

                if wants_code:
                    yield sse_event("tool_log", {"content": "Code-capable mode: deciding whether to run sandbox..."})
                    dataset_rule = (
                        "Dataset context is available. You MUST use existing pandas DataFrame `df` from sandbox and MUST NOT create synthetic/mock DataFrame.\n"
                        if dataset_name
                        else "No dataset context. If user asks data analysis, ask for dataset explicitly.\n"
                    )
                    planner_messages = [
                        {
                            "role": "system",
                            "content": (
                                "You are an assistant with optional Python sandbox execution.\n"
                                "If code execution is needed, return ONLY <PYTHON>...</PYTHON>.\n"
                                "If code is not needed, return ONLY <FINAL>...</FINAL> in Russian.\n"
                                "Do not output anything outside these tags.\n"
                                "For plotting tasks, save figures to files (e.g. output_dir / 'plot.png') and call plt.show().\n"
                                "Never create toy/random sample dataset unless user explicitly asks synthetic demo.\n"
                                f"{dataset_rule}"
                            ),
                        },
                        *[
                            {"role": str(msg.get("role", "user")), "content": str(msg.get("content", ""))}
                            for msg in recent_messages
                        ],
                    ]
                    planner_raw = await llm.chat(messages=planner_messages, purpose="general")
                    code = _extract_python_block(planner_raw)
                    if code:
                        yield sse_event("tool_start", {"name": "sandbox_execution"})
                        exec_result = execute_python_code_general(code=code, run_id=uuid.uuid4().hex, dataset_name=dataset_name)
                        executed_code = code
                        max_retries = 3
                        retry_count = 0
                        while exec_result.get("status") != "success" and retry_count < max_retries:
                            retry_count += 1
                            reason = str(exec_result.get("reason", "")).strip()
                            stderr = str(exec_result.get("stderr", "")).strip()
                            yield sse_event("tool_log", {"content": f"Sandbox retry {retry_count}/{max_retries}: fixing code..."})
                            fix_messages = [
                                {
                                    "role": "system",
                                    "content": (
                                        "Return ONLY <PYTHON>...</PYTHON>.\n"
                                        "Fix the code to run successfully in sandbox.\n"
                                        "Forbidden: os, sys, subprocess, socket, requests, urllib, shutil, pathlib, open(), exec(), eval(), __import__.\n"
                                        "If plotting requested, ensure image is produced via matplotlib (plt.show is allowed)."
                                    ),
                                },
                                {"role": "user", "content": f"Original request:\n{user_text}"},
                                {"role": "user", "content": f"Current code:\n{executed_code}"},
                                {"role": "user", "content": f"Execution status: {exec_result.get('status')}\nReason: {reason}\nStderr:\n{stderr}"},
                            ]
                            retry_raw = await llm.chat(messages=fix_messages, purpose="general")
                            retry_code = _extract_python_block(retry_raw)
                            if not retry_code:
                                break
                            executed_code = retry_code
                            exec_result = execute_python_code_general(
                                code=executed_code,
                                run_id=uuid.uuid4().hex,
                                dataset_name=dataset_name,
                            )
                        yield sse_event("tool_log", {"content": f"Sandbox status: {exec_result.get('status', 'unknown')}"})
                        assistant_blocks.append(
                            {
                                "type": "code",
                                "language": "python",
                                "code": executed_code,
                                "status": exec_result.get("status", "unknown"),
                                "step": 1,
                            } if not no_code_requested else {}
                        )
                        if not no_code_requested:
                            assistant_blocks.append(
                                {
                                    "type": "execution",
                                    "step": 1,
                                    "stdout": str(exec_result.get("stdout", "")),
                                    "stderr": str(exec_result.get("stderr", "")),
                                    "status": exec_result.get("status", "unknown"),
                                    "elapsed_seconds": exec_result.get("elapsed_seconds"),
                                }
                            )
                        files = exec_result.get("files", []) if isinstance(exec_result.get("files"), list) else []
                        for item in files:
                            path = str(item.get("path") or "")
                            name = str(item.get("name") or path.split("/")[-1] or "artifact")
                            if not path:
                                continue
                            artifact = None
                            try:
                                artifact = register_artifact(
                                    user_id=user["id"],
                                    kind=_artifact_kind_by_name(name),
                                    title=name,
                                    path=path,
                                    chat_id=chat_id,
                                    message_id=None,
                                    metadata={"source": "workspace_stream"},
                                )
                                yield sse_event(
                                    "artifact_created",
                                    {
                                        "artifact_id": artifact.get("id"),
                                        "title": artifact.get("title"),
                                        "mime_type": artifact.get("mime_type"),
                                        "preview_url": artifact.get("preview_url"),
                                    },
                                )
                            except Exception:
                                logger.exception("Workspace stream artifact registration failed path=%s", path)
                            if re.search(r"\.(png|jpg|jpeg|webp)$", name, flags=re.IGNORECASE):
                                assistant_blocks.append(
                                    {
                                        "type": "chart",
                                        "title": name,
                                        "url": (artifact.get("preview_url") if artifact else None)
                                        or _image_data_url(path)
                                        or f"/api/lab3/generated-file?path={quote(path, safe='')}",
                                    }
                                )
                            else:
                                assistant_blocks.append(
                                    {
                                        "type": "file",
                                        "title": name,
                                        "filename": name,
                                        "path": path,
                                        **(
                                            {
                                                "preview_url": artifact.get("preview_url"),
                                                "download_url": artifact.get("download_url"),
                                            }
                                            if artifact
                                            else {}
                                        ),
                                    }
                                )
                                table_block = _table_block_from_file(path)
                                if table_block is not None:
                                    assistant_blocks.append(table_block)
                        assistant_blocks = [b for b in assistant_blocks if b]

                        final_messages = [
                            {
                                "role": "system",
                                "content": (
                                    "Answer user in Russian.\n"
                                    "Summarize execution result clearly.\n"
                                    "If stderr is non-empty, mention it."
                                ),
                            },
                            {"role": "user", "content": user_text},
                            {
                                "role": "user",
                                "content": (
                                    f"Executed code:\n{executed_code}\n\n"
                                    f"Status: {exec_result.get('status')}\n"
                                    f"stdout:\n{exec_result.get('stdout', '')}\n"
                                    f"stderr:\n{exec_result.get('stderr', '')}\n"
                                    f"files:\n{files}"
                                ),
                            },
                        ]
                        final_text = await llm.chat(messages=final_messages, purpose="general")
                        final_text = normalize_markdown_tables(final_text)
                        final_text = sanitize_model_final_answer(final_text)
                        yield sse_event("tool_end", {"name": "sandbox_execution", "status": exec_result.get("status", "ok")})
                    else:
                        final_text = _extract_final_block(planner_raw) or planner_raw
                        final_text = normalize_markdown_tables(final_text)
                        final_text = sanitize_model_final_answer(final_text)
                else:
                    llm_messages = [
                        {"role": "system", "content": "You are an assistant. Reply in Russian concisely and clearly."},
                        *[
                            {"role": str(msg.get("role", "user")), "content": str(msg.get("content", ""))}
                            for msg in recent_messages
                        ],
                    ]
                    assembled: list[str] = []
                    async for delta in llm.stream_chat(messages=llm_messages, purpose="general"):
                        if not delta:
                            continue
                        assembled.append(delta)
                        yield sse_event("message_delta", {"content": delta})
                    final_text = "".join(assembled).strip() or "Could not generate response."
                    final_text = normalize_markdown_tables(final_text)
                    final_text = sanitize_model_final_answer(final_text)

                if wants_code:
                    for chunk in chunk_text_for_streaming(final_text):
                        yield sse_event("message_delta", {"content": chunk})

                assistant_message = add_message(
                    user["id"],
                    chat_id,
                    "assistant",
                    final_text,
                    [{"type": "markdown", "content": final_text}, *assistant_blocks],
                    {"streamed": True, "sandbox_mode": wants_code},
                )
                assistant_saved_id = assistant_message["id"]

            yield sse_event("tool_end", {"name": "chat_generation", "status": "success"})
            yield sse_event("done", {"status": "ok", "message_id": assistant_saved_id})
        except (LLMClientError, ValueError):
            logger.exception("Chat streaming failed")
            yield sse_event("error", {"message": "Could not get model response"})
            yield sse_event("done", {"status": "error"})
        except Exception:  # pragma: no cover
            logger.exception("Unexpected chat streaming failure")
            yield sse_event("error", {"message": "Could not get model response"})
            yield sse_event("done", {"status": "error"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.post("/chats/{chat_id}/agent/stream")
async def post_chat_agent_stream(chat_id: str, payload: dict, user: dict = Depends(get_current_user)):
    async def event_generator():
        route = "unknown"
        dataset_name = str(payload.get("dataset_name") or "").strip()
        try:
            chat_state = get_chat(user["id"], chat_id)
            chat = chat_state.get("chat", {})
            dataset_name = str(payload.get("dataset_name") or chat.get("dataset_name") or "").strip()
            question = str(payload.get("question") or "").strip()
            if not dataset_name:
                yield sse_event("error", {"message": "Dataset is required for dataset-agent mode"})
                yield sse_event("done", {"status": "error"})
                return
            if not question:
                yield sse_event("error", {"message": "Question is required"})
                yield sse_event("done", {"status": "error"})
                return

            client_message_id = str(payload.get("client_message_id") or "").strip() or None
            payload_session_id = str(payload.get("session_id") or "").strip()
            effective_session_id = chat_id
            agent_run_id = uuid.uuid4().hex
            create_run(agent_run_id)
            if payload_session_id and payload_session_id != chat_id:
                logger.warning(
                    "Ignoring mismatched session_id for dataset-agent stream: payload_session_id=%s chat_id=%s",
                    payload_session_id,
                    chat_id,
                )
            if client_message_id:
                existing_user_msg = get_message_by_client_id(user["id"], chat_id, "user", client_message_id)
                if existing_user_msg is not None:
                    yield sse_event("tool_log", {"content": "Повторный запрос с тем же client_message_id проигнорирован."})
                    yield sse_event("done", {"status": "ok", "duplicate": True, "message_id": existing_user_msg.get("id")})
                    return
            user_msg = add_message(
                user["id"],
                chat_id,
                "user",
                question,
                [{"type": "markdown", "content": question}],
                {"source": "dataset_agent"},
                client_message_id=client_message_id,
            )
            yield sse_event("message_start", {"chat_id": chat_id, "role": "assistant"})
            yield sse_event("run_started", {"run_id": agent_run_id})
            yield sse_event("tool_start", {"name": "lab3_agent"})
            yield sse_event("tool_log", {"content": "Определяю маршрут запроса..."})

            recent_messages = chat_state.get("messages", [])
            conversation_context = _build_dataset_agent_context(user["id"], chat_id, limit=12)
            followup_intent = _resolve_followup_intent(question, conversation_context)
            resolved_task = str(followup_intent.get("resolved_task") or question)
            last_req = str(conversation_context.get("last_user_analysis_request") or "")
            artifacts_ctx = conversation_context.get("available_artifacts")
            artifacts_count = len(artifacts_ctx) if isinstance(artifacts_ctx, list) else 0
            recent_ctx = conversation_context.get("recent_messages")
            ctx_count = len(recent_ctx) if isinstance(recent_ctx, list) else 0
            logger.info(
                "DATASET_AGENT_CONTEXT chat_id=%s session_id=%s dataset_name=%s current_message=%s "
                "followup_intent=%s resolved_task=%s last_user_analysis_request=%s context_message_count=%s artifact_count=%s",
                chat_id,
                effective_session_id,
                dataset_name,
                question[:240],
                str(followup_intent.get("intent") or "new_task"),
                resolved_task[:300],
                last_req[:240],
                ctx_count,
                artifacts_count,
            )
            router = await route_dataset_chat(
                user_message=question,
                dataset_name=dataset_name,
                recent_messages=recent_messages,
                conversation_context=conversation_context,
                followup_intent=followup_intent,
            )
            route = str(router.get("route") or "answer_directly")
            reason = str(router.get("reason") or "")
            user_intent = str(router.get("user_intent") or "")
            yield sse_event(
                "tool_log",
                {"content": "Маршрут: анализ с code interpreter" if route == "analyze_with_code" else "Маршрут: ответ без кода"},
            )

            if route == "answer_directly":
                final_answer = await _answer_directly_for_dataset_chat(
                    question=resolved_task if followup_intent.get("intent") != "new_task" else question,
                    dataset_name=dataset_name,
                    recent_messages=recent_messages,
                )
                final_answer = normalize_markdown_tables(final_answer)
                final_answer = sanitize_model_final_answer(final_answer)
                for chunk in chunk_text_for_streaming(final_answer):
                    yield sse_event("message_delta", {"content": chunk})
                assistant_message = add_message(
                    user["id"],
                    chat_id,
                    "assistant",
                    final_answer,
                    [{"type": "markdown", "content": final_answer}],
                    {
                        "streamed": True,
                        "sandbox_mode": False,
                        "router": {"route": route, "reason": reason, "user_intent": user_intent},
                    },
                )
                yield sse_event("tool_end", {"name": "lab3_agent", "status": "success"})
                yield sse_event("done", {"status": "ok", "message_id": assistant_message.get("id")})
                return

            result = await ask_agent(
                dataset_name=dataset_name,
                question=question,
                column_overrides=payload.get("column_overrides") or {},
                max_tool_calls=int(payload.get("max_tool_calls") or 6),
                use_critic=bool(payload.get("use_critic") or False),
                analysis_mode=str(payload.get("analysis_mode") or "code_interpreter"),
                session_id=effective_session_id,
                include_history=bool(payload.get("include_history", True)),
                reset_session_flag=bool(payload.get("reset_session", False)),
                max_code_steps=payload.get("max_code_steps"),
                conversation_context=conversation_context,
                resolved_task=resolved_task,
                followup_intent=followup_intent,
                user_id=user["id"],
                run_id=agent_run_id,
            )
            result_status = str(result.get("status") or "").strip().lower()
            if result_status == "cancelled":
                cancel_text = "Запрос остановлен пользователем."
                assistant_message = add_message(
                    user["id"],
                    chat_id,
                    "assistant",
                    cancel_text,
                    [{"type": "warning", "content": cancel_text}],
                    {
                        "streamed": True,
                        "cancelled": True,
                        "run_id": result.get("run_id") or agent_run_id,
                        "router": {"route": route, "reason": reason, "user_intent": user_intent},
                    },
                )
                yield sse_event("cancelled", {"message": cancel_text, "run_id": result.get("run_id") or agent_run_id})
                yield sse_event("done", {"status": "cancelled", "message_id": assistant_message.get("id")})
                return
            if result_status in {"error", "failed_contract"}:
                error_text = str(result.get("final_answer") or "Модель не сгенерировала исполняемый Python-код для анализа.").strip()
                error_block = {"type": "warning", "content": error_text}
                assistant_message = add_message(
                    user["id"],
                    chat_id,
                    "assistant",
                    error_text,
                    [error_block],
                    {
                        "streamed": True,
                        "sandbox_mode": True,
                        "session_id": result.get("session_id") or chat_id,
                        "router": {"route": route, "reason": reason, "user_intent": user_intent},
                        "run_id": agent_run_id,
                        "raw_messages": result.get("raw_messages", []),
                        "debug_warnings": result.get("debug_warnings", []),
                        "warnings": result.get("warnings", []),
                    },
                )
                yield sse_event("tool_log", {"content": error_text})
                yield sse_event("error", {"message": error_text})
                yield sse_event("tool_end", {"name": "lab3_agent", "status": "error"})
                yield sse_event("done", {"status": "error", "message_id": assistant_message.get("id")})
                return

            infra_error: str | None = None
            code_steps = result.get("code_steps") or result.get("steps") or []
            if isinstance(code_steps, list):
                for step in code_steps:
                    if not isinstance(step, dict):
                        continue
                    execution = step.get("execution") if isinstance(step.get("execution"), dict) else {}
                    stderr = str(execution.get("stderr") or "")
                    if "Sandbox Docker runner is not available" in stderr:
                        infra_error = stderr.strip()
                        break
            if infra_error:
                raise RuntimeError(infra_error)
            if isinstance(code_steps, list):
                for idx, step in enumerate(code_steps, start=1):
                    if not isinstance(step, dict):
                        continue
                    code = str(step.get("code") or "").strip()
                    if not code:
                        continue
                    preview_lines = code.splitlines()[:12]
                    preview = "\n".join(preview_lines)
                    yield sse_event(
                        "code_preview",
                        {
                            "step": int(step.get("step") or idx),
                            "language": "python",
                            "preview": preview,
                            "code": code,
                        },
                    )
                    execution = step.get("execution") if isinstance(step.get("execution"), dict) else {}
                    yield sse_event(
                        "code_executed",
                        {
                            "step": int(step.get("step") or idx),
                            "status": str(execution.get("status") or step.get("status") or "unknown"),
                        },
                    )

            final_answer = str(result.get("final_answer") or "")
            if not final_answer.strip():
                final_answer = "Не удалось получить текстовый ответ после выполнения анализа."
            final_answer = normalize_markdown_tables(final_answer)
            final_answer = sanitize_model_final_answer(final_answer)
            for chunk in chunk_text_for_streaming(final_answer):
                yield sse_event("message_delta", {"content": chunk})

            artifacts: list[dict] = []
            merged_files_map: dict[str, dict] = {}
            files_before = 0
            for file_item in (result.get("files") or []):
                if isinstance(file_item, dict):
                    files_before += 1
                    key = _file_dedupe_key(file_item)
                    if key:
                        merged_files_map[key] = file_item
            if isinstance(code_steps, list):
                for step in code_steps:
                    if not isinstance(step, dict):
                        continue
                    execution = step.get("execution") if isinstance(step.get("execution"), dict) else {}
                    for file_item in (execution.get("files") or []):
                        if isinstance(file_item, dict):
                            files_before += 1
                            key = _file_dedupe_key(file_item)
                            if key and key not in merged_files_map:
                                merged_files_map[key] = file_item
            logger.info(
                "LAB3_FILES_DEDUP before=%s after=%s keys=%s",
                files_before,
                len(merged_files_map),
                list(merged_files_map.keys())[:40],
            )

            for file_item in merged_files_map.values():
                path = str(file_item.get("path") or "")
                name = str(file_item.get("name") or Path(path).name or "artifact")
                if not path:
                    continue
                try:
                    artifact = register_artifact(
                        user_id=user["id"],
                        kind=_artifact_kind_by_name(name),
                        title=name,
                        path=path,
                        chat_id=chat_id,
                        message_id=None,
                        metadata={"source": "chat_agent_stream", "dataset_message_id": user_msg["id"]},
                    )
                    artifacts.append(artifact)
                    yield sse_event(
                        "artifact_created",
                        {
                            "artifact_id": artifact.get("id"),
                            "kind": artifact.get("kind"),
                            "title": artifact.get("title"),
                            "filename": artifact.get("filename"),
                            "mime_type": artifact.get("mime_type"),
                            "preview_url": artifact.get("preview_url"),
                            "download_url": artifact.get("download_url"),
                        },
                    )
                except Exception:
                    logger.exception("Agent stream artifact registration failed path=%s", path)

            artifacts_before = len(artifacts)
            dedup_artifacts: list[dict] = []
            seen_artifacts: set[str] = set()
            artifact_keys: list[str] = []
            for artifact in artifacts:
                if not isinstance(artifact, dict):
                    continue
                key = _artifact_dedupe_key(artifact)
                if key in seen_artifacts:
                    continue
                seen_artifacts.add(key)
                artifact_keys.append(key)
                dedup_artifacts.append(artifact)
            artifacts = dedup_artifacts

            overview_blocks: list[dict] = []
            if _is_dataset_overview_request(question):
                try:
                    overview_blocks = _build_dataset_overview_blocks(dataset_name, user["id"])
                except Exception:
                    logger.exception("Failed to build dataset overview blocks")
            execution_blocks: list[dict] = []
            if isinstance(code_steps, list):
                for idx, step in enumerate(code_steps, start=1):
                    if not isinstance(step, dict):
                        continue
                    code = str(step.get("code") or "").strip()
                    execution = step.get("execution") if isinstance(step.get("execution"), dict) else {}
                    if code:
                        execution_blocks.append(
                            {
                                "type": "code",
                                "language": "python",
                                "code": code,
                                "status": str(execution.get("status") or step.get("status") or "unknown"),
                                "step": int(step.get("step") or idx),
                            }
                        )
                    execution_blocks.append(
                        {
                            "type": "execution",
                            "step": int(step.get("step") or idx),
                            "stdout": str(execution.get("stdout") or ""),
                            "stderr": str(execution.get("stderr") or ""),
                            "status": str(execution.get("status") or step.get("status") or "unknown"),
                            "elapsed_seconds": execution.get("elapsed_seconds"),
                            "files": execution.get("files") if isinstance(execution.get("files"), list) else [],
                        }
                    )

            artifact_blocks = [artifact_to_message_block(user["id"], a) for a in artifacts]
            blocks_before = len(artifact_blocks)
            has_table_artifact_block = any(
                isinstance(b, dict) and b.get("type") == "table"
                for b in artifact_blocks
            )
            # Avoid duplicated dataset previews: if execution already produced table artifacts
            # (e.g. head.csv), render artifact tables as the single source of truth.
            if has_table_artifact_block:
                overview_blocks = []
            chart_blocks_raw = [b for b in artifact_blocks if isinstance(b, dict) and b.get("type") == "chart"]
            chart_blocks: list[dict] = []
            seen_chart: set[str] = set()
            for block in chart_blocks_raw:
                key = _chart_block_dedupe_key(block)
                if key in seen_chart:
                    continue
                seen_chart.add(key)
                chart_blocks.append(block)
            other_artifact_blocks = [b for b in artifact_blocks if isinstance(b, dict) and b.get("type") != "chart"]
            logger.info(
                "LAB3_ARTIFACT_BLOCKS_DEDUP before=%s after=%s keys=%s artifacts_before=%s artifacts_after=%s",
                blocks_before,
                len(chart_blocks) + len(other_artifact_blocks),
                artifact_keys[:40],
                artifacts_before,
                len(artifacts),
            )
            blocks = [{"type": "markdown", "content": final_answer}, *chart_blocks, *overview_blocks, *other_artifact_blocks, *execution_blocks]
            logger.info("LAB3_CHAT_MESSAGE_BLOCKS block_types=%s", [str(b.get("type")) for b in blocks if isinstance(b, dict)])
            assistant_message = add_message(
                user["id"],
                chat_id,
                "assistant",
                final_answer,
                blocks,
                    {
                        "streamed": True,
                        "sandbox_mode": True,
                        "session_id": result.get("session_id") or chat_id,
                        "router": {"route": route, "reason": reason, "user_intent": user_intent},
                        "run_id": result.get("run_id") or agent_run_id,
                        "generated_files": result.get("files", []),
                        "code_steps": code_steps if isinstance(code_steps, list) else [],
                        "successful_executions_count": result.get("successful_executions_count", 0),
                    },
                )
            yield sse_event("tool_end", {"name": "lab3_agent", "status": "success"})
            yield sse_event(
                "done",
                {
                    "status": "ok",
                    "message_id": assistant_message.get("id"),
                    "session_id": result.get("session_id") or chat_id,
                },
            )
        except Exception as exc:
            logger.exception("Dataset-agent stream failed")
            error_type = exc.__class__.__name__
            error_message = _sanitize_error_text(str(exc or "").strip() or "unknown error")
            traceback_full = _sanitize_error_text(traceback.format_exc())
            traceback_lines = traceback_full.splitlines()
            traceback_preview = "\n".join(traceback_lines[-40:]) if traceback_lines else ""
            user_message = f"Ошибка dataset-agent: {error_message}" if error_message else "Ошибка dataset-agent: неизвестная ошибка"
            try:
                _ = add_message(
                    user["id"],
                    chat_id,
                    "assistant",
                    user_message,
                    [
                        {
                            "type": "warning",
                            "content": user_message,
                            "details": traceback_preview,
                            "error_type": error_type,
                        }
                    ],
                    {
                        "streamed": True,
                        "error": True,
                        "error_type": error_type,
                        "error_message": error_message,
                        "traceback": traceback_preview,
                        "route": route,
                        "dataset_name": dataset_name,
                    },
                )
            except Exception:
                logger.exception("Failed to persist error message")
            yield sse_event("tool_log", {"content": user_message})
            yield sse_event("error", {"message": user_message, "error_type": error_type, "error_message": error_message})
            yield sse_event("done", {"status": "error"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.post("/agent-runs/{run_id}/cancel")
def cancel_agent_run(run_id: str, user: dict = Depends(get_current_user)):
    _ = user
    was_found = cancel_run(run_id)
    for container_name in get_container_names(run_id):
        try:
            subprocess.run(
                ["docker", "stop", container_name],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
        except Exception:
            logger.exception("Failed to stop sandbox container during cancellation: run_id=%s container=%s", run_id, container_name)
    return {"status": "cancelled" if was_found else "not_found", "run_id": run_id}


@router.patch("/chats/{chat_id}", response_model=ChatItem)
def patch_chat(chat_id: str, payload: UpdateChatRequest, user: dict = Depends(get_current_user)) -> ChatItem:
    try:
        item = update_chat(user["id"], chat_id, payload.title, payload.archived, payload.dataset_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ChatItem.model_validate(item)


@router.delete("/chats/{chat_id}", response_model=ChatItem)
def delete_chat(chat_id: str, user: dict = Depends(get_current_user)) -> ChatItem:
    try:
        item = archive_chat(user["id"], chat_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ChatItem.model_validate(item)
