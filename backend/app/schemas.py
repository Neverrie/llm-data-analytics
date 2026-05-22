from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str


class AuthRegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class UserPublic(BaseModel):
    id: str
    email: str
    display_name: str
    is_demo: bool


class AuthResponse(BaseModel):
    user: UserPublic
    access_token: str
    token_type: str = "bearer"


class WorkspaceCounts(BaseModel):
    chats: int
    datasets: int
    artifacts: int


class ChatItem(BaseModel):
    id: str
    title: str
    kind: str
    dataset_name: str | None = None
    created_at: str
    updated_at: str
    archived: bool = False


class WorkspaceResponse(BaseModel):
    user: UserPublic
    counts: WorkspaceCounts
    recent_chats: list[ChatItem]
    recent_artifacts: list[dict[str, Any]]


class ChatsResponse(BaseModel):
    items: list[ChatItem]


class CreateChatRequest(BaseModel):
    title: str
    kind: str
    dataset_name: str | None = None


class ChatMessageCreateRequest(BaseModel):
    role: str
    content: str
    blocks: list[Any] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    client_message_id: str | None = None


class ChatMessageItem(BaseModel):
    id: str
    chat_id: str
    role: str
    content: str
    blocks: list[Any] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ChatDetailResponse(BaseModel):
    chat: ChatItem
    messages: list[ChatMessageItem]


class UpdateChatRequest(BaseModel):
    title: str | None = None
    archived: bool | None = None
    dataset_name: str | None = None


class ArtifactRegisterRequest(BaseModel):
    kind: str
    title: str
    path: str
    chat_id: str | None = None
    message_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatAgentStreamRequest(BaseModel):
    question: str
    dataset_path: str | None = None
    max_steps: int = Field(default=30, ge=1, le=30)
    client_message_id: str | None = None

