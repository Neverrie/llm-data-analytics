from fastapi import APIRouter, Depends, HTTPException, Query

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
from app.services.auth_service import get_current_user, user_public
from app.services.workspace_service import add_message, archive_chat, create_chat, get_chat, list_chats, update_chat, workspace_overview

router = APIRouter(tags=["workspace"])


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
