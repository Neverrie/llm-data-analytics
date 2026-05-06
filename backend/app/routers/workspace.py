import logging
import json
import base64
import re
import uuid
from pathlib import Path
from urllib.parse import quote

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
from app.services.artifact_service import register_artifact
from app.services.auth_service import get_current_user, user_public
from app.services.code_sandbox import execute_python_code_general
from app.services.llm_client import LLMClient, LLMClientError
from app.services.workspace_service import add_message, archive_chat, create_chat, get_chat, list_chats, update_chat, workspace_overview
from app.stream_events import chunk_text_for_streaming, sse_event

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
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
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
