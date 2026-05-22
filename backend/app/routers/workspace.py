import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas import ChatDetailResponse, ChatItem, ChatMessageCreateRequest, ChatMessageItem, ChatsResponse, CreateChatRequest, UpdateChatRequest, UserPublic, WorkspaceCounts, WorkspaceResponse
from app.services.auth_service import get_current_user, user_public
from app.services.workspace_service import add_message, archive_chat, create_chat, get_chat, list_chats, update_chat, workspace_overview

router = APIRouter(tags=["workspace"])


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
        try:
            user_msg = add_message(user["id"], chat_id, "user", payload.content, payload.blocks, payload.metadata, payload.client_message_id)
            yield sse("message_saved", {"message_id": user_msg["id"]})
            answer = "Agent and lab logic were removed. Backend is in minimal mode."
            for i in range(0, len(answer), 48):
                yield sse("message_delta", {"content": answer[i:i + 48]})
            assistant = add_message(user["id"], chat_id, "assistant", answer, [{"type": "markdown", "content": answer}], {"minimal_mode": True})
            yield sse("done", {"status": "ok", "message_id": assistant["id"]})
        except Exception as exc:
            yield sse("error", {"message": str(exc)})
            yield sse("done", {"status": "error"})

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/chats/{chat_id}/agent/stream")
def stream_agent(chat_id: str, user: dict = Depends(get_current_user)):
    _ = chat_id
    _ = user

    def gen():
        yield "event: error\ndata: {\"message\": \"Lab/agent features are removed from current implementation.\"}\n\n"
        yield "event: done\ndata: {\"status\": \"error\"}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/agent-runs/{run_id}/cancel")
def cancel_agent_run(run_id: str, user: dict = Depends(get_current_user)):
    _ = user
    return {"status": "not_found", "run_id": run_id}


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
