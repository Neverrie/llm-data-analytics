import json
import threading
import queue

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.agents.dataset_agent import run_dataset_agent
from app.db import fetch_all, fetch_one, get_connection
from app.schemas import ChatAgentStreamRequest, ChatDetailResponse, ChatItem, ChatMessageCreateRequest, ChatMessageItem, ChatsResponse, CreateChatRequest, UpdateChatRequest, UserPublic, WorkspaceCounts, WorkspaceResponse
from app.services.artifact_service import artifact_to_message_block, register_artifact
from app.services.auth_service import get_current_user, user_public
from app.services.workspace_service import add_message, archive_chat, create_chat, get_chat, list_chats, update_chat, workspace_overview

router = APIRouter(tags=["workspace"])
_chat_cancel_events: dict[str, threading.Event] = {}


def _build_agent_memory(messages: list[dict], max_items: int = 20) -> str:
    picked = messages[-max_items:]
    lines: list[str] = []
    for m in picked:
        role = str(m.get("role") or "")
        content = str(m.get("content") or "").strip()
        if content:
            short = content.replace("\n", " ")
            if len(short) > 320:
                short = short[:320] + "..."
            lines.append(f"{role}: {short}")
        blocks = m.get("blocks") or []
        if isinstance(blocks, list):
            exec_count = sum(1 for b in blocks if isinstance(b, dict) and b.get("type") == "execution")
            if exec_count:
                lines.append(f"{role}: execution_blocks={exec_count}")
    return "\n".join(lines)


def _to_chat_item(item: dict) -> ChatItem:
    return ChatItem.model_validate(item)


def _to_msg_item(item: dict) -> ChatMessageItem:
    return ChatMessageItem.model_validate(item)


@router.get("/workspace", response_model=WorkspaceResponse)
def get_workspace(user: dict = Depends(get_current_user)) -> WorkspaceResponse:
    data = workspace_overview(user["id"])
    return WorkspaceResponse(
        user=UserPublic.model_validate(user_public(user)),
        counts=WorkspaceCounts.model_validate(data["counts"]),
        recent_chats=[_to_chat_item(x) for x in data["recent_chats"]],
        recent_artifacts=data["recent_artifacts"],
    )


@router.get("/chats", response_model=ChatsResponse)
def get_chats(kind: str | None = None, archived: bool | None = None, user: dict = Depends(get_current_user)) -> ChatsResponse:
    return ChatsResponse(items=[_to_chat_item(x) for x in list_chats(user["id"], kind, archived)])


@router.post("/chats", response_model=ChatItem)
def post_chat(payload: CreateChatRequest, user: dict = Depends(get_current_user)) -> ChatItem:
    return _to_chat_item(create_chat(user["id"], payload.title, payload.kind, payload.dataset_name))


@router.get("/chats/{chat_id}", response_model=ChatDetailResponse)
def get_chat_detail(chat_id: str, user: dict = Depends(get_current_user)) -> ChatDetailResponse:
    try:
        data = get_chat(user["id"], chat_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ChatDetailResponse(chat=_to_chat_item(data["chat"]), messages=[_to_msg_item(x) for x in data["messages"]])


@router.post("/chats/{chat_id}/messages", response_model=ChatMessageItem)
def post_message(chat_id: str, payload: ChatMessageCreateRequest, user: dict = Depends(get_current_user)) -> ChatMessageItem:
    try:
        msg = add_message(user["id"], chat_id, payload.role, payload.content, payload.blocks, payload.metadata, payload.client_message_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_msg_item(msg)


@router.post("/chats/{chat_id}/messages/stream")
def stream_message(chat_id: str, payload: ChatMessageCreateRequest, user: dict = Depends(get_current_user)):
    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    def gen():
        cancel_event = threading.Event()
        _chat_cancel_events[chat_id] = cancel_event
        try:
            user_msg = add_message(
                user["id"],
                chat_id,
                "user",
                payload.content,
                payload.blocks or [{"type": "markdown", "content": payload.content}],
                payload.metadata,
                payload.client_message_id,
            )
            yield sse("message_saved", {"message_id": user_msg["id"]})

            chat_data = get_chat(user["id"], chat_id)
            conversation_context = _build_agent_memory(chat_data.get("messages") or [], max_items=24)
            chat_dataset_name = (chat_data.get("chat") or {}).get("dataset_name")
            dataset_path = None
            existing_artifacts: list[dict] = []
            if chat_dataset_name:
                with get_connection() as conn:
                    ds = fetch_one(
                        conn,
                        "SELECT path FROM datasets WHERE name = ? AND (user_id = ? OR user_id IS NULL) ORDER BY created_at DESC LIMIT 1",
                        (chat_dataset_name, user["id"]),
                    )
                if ds and ds.get("path"):
                    dataset_path = str(ds["path"])
            with get_connection() as conn:
                art_rows = fetch_all(
                    conn,
                    "SELECT id, kind, title, filename, created_at FROM artifacts WHERE user_id = ? AND chat_id = ? ORDER BY created_at DESC LIMIT 30",
                    (user["id"], chat_id),
                )
            existing_artifacts = [dict(x) for x in art_rows]

            yield sse("agent_status", {"stage": "started", "message": "Agent started"})
            event_queue: queue.Queue[tuple[str, dict]] = queue.Queue()
            holder: dict[str, object] = {"result": None, "error": None}

            def on_agent_event(data: dict):
                event_queue.put(("agent_status", data))

            def run_agent_worker():
                try:
                    holder["result"] = run_dataset_agent(
                        chat_id=chat_id,
                        user_message=payload.content,
                        dataset_path=dataset_path,
                        max_steps=30,
                        should_cancel=cancel_event.is_set,
                        on_event=on_agent_event,
                        conversation_context=conversation_context,
                        existing_artifacts=existing_artifacts,
                    )
                except Exception as exc:
                    holder["error"] = exc
                finally:
                    event_queue.put(("agent_finished", {}))

            worker = threading.Thread(target=run_agent_worker, daemon=True)
            worker.start()
            worker_done = False
            while not worker_done:
                try:
                    evt_name, evt_data = event_queue.get(timeout=0.25)
                except queue.Empty:
                    worker_done = not worker.is_alive()
                    continue
                if evt_name == "agent_finished":
                    worker_done = True
                else:
                    yield sse(evt_name, evt_data)

            worker.join(timeout=0.1)
            if holder["error"] is not None:
                raise holder["error"]  # type: ignore[misc]
            if holder["result"] is None:
                raise RuntimeError("Agent did not produce result")
            agent_result = holder["result"]

            artifacts: list[dict] = []

            for f in agent_result.files:
                try:
                    path = str(f.get("path") or "")
                    if not path:
                        continue
                    filename = str(f.get("filename") or "artifact")
                    kind = "chart" if filename.lower().endswith((".png", ".jpg", ".jpeg")) else "table" if filename.lower().endswith((".csv", ".json", ".xlsx")) else "other"
                    art = register_artifact(
                        user_id=user["id"],
                        kind=kind,
                        title=filename,
                        path=path,
                        chat_id=chat_id,
                        message_id=None,
                        metadata={"source": "agent_loop"},
                    )
                    artifacts.append(art)
                    yield sse("artifact_created", {"artifact_id": art.get("id"), "filename": art.get("filename"), "kind": art.get("kind")})
                except Exception:
                    continue

            text = agent_result.final_answer or ""
            for i in range(0, len(text), 80):
                yield sse("message_delta", {"content": text[i:i + 80]})

            blocks: list[dict] = [{"type": "markdown", "content": text}]
            for art in artifacts:
                blocks.append(artifact_to_message_block(user["id"], art))
            for st in agent_result.steps:
                if st.type == "tool":
                    tool_payload = st.content.get("result", {}) if isinstance(st.content, dict) else {}
                    content = tool_payload.get("content") if isinstance(tool_payload, dict) else {}
                    tool_status = str(tool_payload.get("status") or "")
                    tool_error = str(tool_payload.get("error") or "")
                    if isinstance(content, dict):
                        blocks.append({
                            "type": "execution",
                            "step": st.step_index,
                            "status": str(content.get("sandbox_status") or tool_status or "error"),
                            "stdout": str(content.get("stdout") or ""),
                            "stderr": str(content.get("stderr") or tool_error or ""),
                            "files": content.get("files") or [],
                            "elapsed_seconds": content.get("elapsed_seconds"),
                        })
                    else:
                        blocks.append({
                            "type": "execution",
                            "step": st.step_index,
                            "status": tool_status or "error",
                            "stdout": "",
                            "stderr": tool_error or "Tool execution failed",
                            "files": [],
                            "elapsed_seconds": None,
                        })
                    code_text = ""
                    if isinstance(st.content, dict):
                        code_text = str(st.content.get("tool_arguments", {}).get("code") or "")
                    if code_text:
                        blocks.append({"type": "code", "language": "python", "code": code_text, "step": st.step_index})

            assistant = add_message(
                user["id"],
                chat_id,
                "assistant",
                text,
                blocks,
                {
                    "agent_status": agent_result.status,
                    "steps": [s.model_dump() for s in agent_result.steps],
                    "files": agent_result.files,
                },
            )
            done_status = "cancelled" if agent_result.status == "cancelled" else "ok"
            yield sse("done", {"status": done_status, "message_id": assistant["id"], "agent_status": agent_result.status})
        except Exception as exc:
            yield sse("error", {"message": str(exc)})
            yield sse("done", {"status": "error"})
        finally:
            _chat_cancel_events.pop(chat_id, None)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/chats/{chat_id}/agent/stream")
def stream_agent(chat_id: str, payload: ChatAgentStreamRequest, user: dict = Depends(get_current_user)):
    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    def gen():
        cancel_event = threading.Event()
        _chat_cancel_events[chat_id] = cancel_event
        try:
            user_msg = add_message(
                user["id"],
                chat_id,
                "user",
                payload.question,
                [{"type": "markdown", "content": payload.question}],
                {"agent": True},
                payload.client_message_id,
            )
            yield sse("message_saved", {"message_id": user_msg["id"]})
            chat_data = get_chat(user["id"], chat_id)
            conversation_context = _build_agent_memory(chat_data.get("messages") or [], max_items=24)
            dataset_path = payload.dataset_path
            if not dataset_path:
                chat_dataset_name = (chat_data.get("chat") or {}).get("dataset_name")
                if chat_dataset_name:
                    with get_connection() as conn:
                        ds = fetch_one(
                            conn,
                            "SELECT path FROM datasets WHERE name = ? AND (user_id = ? OR user_id IS NULL) ORDER BY created_at DESC LIMIT 1",
                            (chat_dataset_name, user["id"]),
                        )
                    if ds and ds.get("path"):
                        dataset_path = str(ds["path"])
            with get_connection() as conn:
                art_rows = fetch_all(
                    conn,
                    "SELECT id, kind, title, filename, created_at FROM artifacts WHERE user_id = ? AND chat_id = ? ORDER BY created_at DESC LIMIT 30",
                    (user["id"], chat_id),
                )
            existing_artifacts = [dict(x) for x in art_rows]

            yield sse("agent_status", {"stage": "started", "message": "Agent started"})
            event_queue: queue.Queue[tuple[str, dict]] = queue.Queue()
            holder: dict[str, object] = {"result": None, "error": None}

            def on_agent_event(data: dict):
                event_queue.put(("agent_status", data))

            def run_agent_worker():
                try:
                    holder["result"] = run_dataset_agent(
                        chat_id=chat_id,
                        user_message=payload.question,
                        dataset_path=dataset_path,
                        max_steps=payload.max_steps,
                        should_cancel=cancel_event.is_set,
                        on_event=on_agent_event,
                        conversation_context=conversation_context,
                        existing_artifacts=existing_artifacts,
                    )
                except Exception as exc:
                    holder["error"] = exc
                finally:
                    event_queue.put(("agent_finished", {}))

            worker = threading.Thread(target=run_agent_worker, daemon=True)
            worker.start()
            worker_done = False
            while not worker_done:
                try:
                    evt_name, evt_data = event_queue.get(timeout=0.25)
                except queue.Empty:
                    worker_done = not worker.is_alive()
                    continue
                if evt_name == "agent_finished":
                    worker_done = True
                else:
                    yield sse(evt_name, evt_data)

            worker.join(timeout=0.1)
            if holder["error"] is not None:
                raise holder["error"]  # type: ignore[misc]
            if holder["result"] is None:
                raise RuntimeError("Agent did not produce result")
            agent_result = holder["result"]

            artifacts: list[dict] = []
            for f in agent_result.files:
                try:
                    path = str(f.get("path") or "")
                    if not path:
                        continue
                    filename = str(f.get("filename") or "artifact")
                    kind = "chart" if filename.lower().endswith((".png", ".jpg", ".jpeg")) else "table" if filename.lower().endswith((".csv", ".json", ".xlsx")) else "other"
                    art = register_artifact(
                        user_id=user["id"],
                        kind=kind,
                        title=filename,
                        path=path,
                        chat_id=chat_id,
                        message_id=None,
                        metadata={"source": "agent_loop"},
                    )
                    artifacts.append(art)
                    yield sse("artifact_created", {"artifact_id": art.get("id"), "filename": art.get("filename"), "kind": art.get("kind")})
                except Exception:
                    continue

            text = agent_result.final_answer or ""
            for i in range(0, len(text), 80):
                yield sse("message_delta", {"content": text[i:i + 80]})

            blocks: list[dict] = [{"type": "markdown", "content": text}]
            for art in artifacts:
                blocks.append(artifact_to_message_block(user["id"], art))

            for st in agent_result.steps:
                if st.type == "tool":
                    tool_payload = st.content.get("result", {}) if isinstance(st.content, dict) else {}
                    content = tool_payload.get("content") if isinstance(tool_payload, dict) else {}
                    tool_status = str(tool_payload.get("status") or "")
                    tool_error = str(tool_payload.get("error") or "")
                    if isinstance(content, dict):
                        stdout = str(content.get("stdout") or "")
                        stderr = str(content.get("stderr") or "")
                        blocks.append({
                            "type": "execution",
                            "step": st.step_index,
                            "status": str(content.get("sandbox_status") or tool_status or "error"),
                            "stdout": stdout,
                            "stderr": stderr or tool_error,
                            "files": content.get("files") or [],
                            "elapsed_seconds": content.get("elapsed_seconds"),
                        })
                    else:
                        blocks.append({
                            "type": "execution",
                            "step": st.step_index,
                            "status": tool_status or "error",
                            "stdout": "",
                            "stderr": tool_error or "Tool execution failed",
                            "files": [],
                            "elapsed_seconds": None,
                        })
                    code_text = ""
                    if isinstance(st.content, dict):
                        code_text = str(st.content.get("tool_arguments", {}).get("code") or "")
                    if code_text:
                        blocks.append({"type": "code", "language": "python", "code": code_text, "step": st.step_index})

            assistant = add_message(
                user["id"],
                chat_id,
                "assistant",
                text,
                blocks,
                {
                    "agent_status": agent_result.status,
                    "steps": [s.model_dump() for s in agent_result.steps],
                    "files": agent_result.files,
                },
            )
            done_status = "cancelled" if agent_result.status == "cancelled" else "ok"
            yield sse("done", {"status": done_status, "message_id": assistant["id"], "agent_status": agent_result.status})
        except Exception as exc:
            yield sse("error", {"message": str(exc)})
            yield sse("done", {"status": "error"})
        finally:
            _chat_cancel_events.pop(chat_id, None)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/agent-runs/{run_id}/cancel")
def cancel_agent_run(run_id: str, user: dict = Depends(get_current_user)):
    _ = user
    return {"status": "not_implemented", "run_id": run_id}


@router.post("/chats/{chat_id}/cancel")
def cancel_chat_run(chat_id: str, user: dict = Depends(get_current_user)):
    _ = user
    event = _chat_cancel_events.get(chat_id)
    if event is None:
        return {"status": "idle", "chat_id": chat_id}
    event.set()
    return {"status": "cancelling", "chat_id": chat_id}


@router.patch("/chats/{chat_id}", response_model=ChatItem)
def patch_chat(chat_id: str, payload: UpdateChatRequest, user: dict = Depends(get_current_user)) -> ChatItem:
    try:
        item = update_chat(user["id"], chat_id, payload.title, payload.archived, payload.dataset_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_chat_item(item)


@router.delete("/chats/{chat_id}", response_model=ChatItem)
def delete_chat(chat_id: str, user: dict = Depends(get_current_user)) -> ChatItem:
    try:
        item = archive_chat(user["id"], chat_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_chat_item(item)



