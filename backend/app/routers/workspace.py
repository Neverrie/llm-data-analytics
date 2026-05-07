import logging
import json
import base64
import re
import uuid
from pathlib import Path
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
from app.services.lab3_service import ask_agent
from app.services.llm_client import LLMClient, LLMClientError
from app.services.workspace_service import add_message, archive_chat, create_chat, get_chat, list_chats, update_chat, workspace_overview
from app.stream_events import chunk_text_for_streaming, sse_event
from app.config import settings

router = APIRouter(tags=["workspace"])
logger = logging.getLogger(__name__)


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
    low = (question or "").lower()
    return any(token in low for token in ["что скажешь по датасету", "обзор датасета", "опиши датасет", "какие колонки", "первые строки"])


def _build_dataset_overview_blocks(dataset_name: str) -> list[dict]:
    dataset_path = (Path(settings.datasets_dir) / dataset_name).resolve()
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
        item = add_message(user["id"], chat_id, payload.role, payload.content, payload.blocks, payload.metadata)
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

            _ = add_message(user["id"], chat_id, payload.role, payload.content, payload.blocks, payload.metadata)

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
                        yield sse_event("tool_end", {"name": "sandbox_execution", "status": exec_result.get("status", "ok")})
                    else:
                        final_text = _extract_final_block(planner_raw) or planner_raw
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

            user_msg = add_message(
                user["id"],
                chat_id,
                "user",
                question,
                [{"type": "markdown", "content": question}],
                {"source": "dataset_agent"},
            )
            yield sse_event("message_start", {"chat_id": chat_id, "role": "assistant"})
            yield sse_event("tool_start", {"name": "lab3_agent"})
            yield sse_event("tool_log", {"content": "Определяю маршрут запроса..."})

            recent_messages = chat_state.get("messages", [])
            router = await route_dataset_chat(
                user_message=question,
                dataset_name=dataset_name,
                recent_messages=recent_messages,
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
                    question=question,
                    dataset_name=dataset_name,
                    recent_messages=recent_messages,
                )
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
                session_id=str(payload.get("session_id") or chat_id),
                include_history=bool(payload.get("include_history", True)),
                reset_session_flag=bool(payload.get("reset_session", False)),
                max_code_steps=payload.get("max_code_steps"),
            )
            result_status = str(result.get("status") or "").strip().lower()
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
            for chunk in chunk_text_for_streaming(final_answer):
                yield sse_event("message_delta", {"content": chunk})

            artifacts: list[dict] = []
            for file_item in (result.get("files") or []):
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

            overview_blocks: list[dict] = []
            if _is_dataset_overview_request(question):
                try:
                    overview_blocks = _build_dataset_overview_blocks(dataset_name)
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
                        }
                    )

            blocks = [
                {"type": "markdown", "content": final_answer},
                *execution_blocks,
                *overview_blocks,
                *[artifact_to_message_block(user["id"], a) for a in artifacts],
            ]
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
            err_text = str(exc or "")
            message = err_text if "Sandbox Docker runner is not available" in err_text else "Не удалось получить ответ модели"
            try:
                _ = add_message(
                    user["id"],
                    chat_id,
                    "assistant",
                    f"Ошибка sandbox: {message}" if "Sandbox Docker runner is not available" in message else message,
                    [{"type": "warning", "content": f"Ошибка sandbox: {message}" if "Sandbox Docker runner is not available" in message else message}],
                    {"streamed": True, "error": True},
                )
            except Exception:
                logger.exception("Failed to persist error message")
            yield sse_event("tool_log", {"content": message})
            yield sse_event("error", {"message": message})
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
