from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    service: str


class Lab1StatusResponse(BaseModel):
    lab: int
    name: str
    status: str
    planned_features: list[str]


class Lab2RunRequest(BaseModel):
    limit: int = Field(default=20, ge=1)
    min_score: int | None = Field(default=None, ge=1, le=5)
    max_score: int | None = Field(default=None, ge=1, le=5)
    batch_size: int | None = Field(default=None, ge=1, le=200)
    process_all: bool = False


class UberReviewInput(BaseModel):
    row_id: int
    content: str
    score: float | int | None = None
    thumbs_up_count: int | None = None
    review_created_version: str | None = None
    at: str | None = None
    app_version: str | None = None


class ReviewClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row_id: int
    sentiment: Literal["positive", "negative", "neutral", "mixed"]
    issue_type: str
    topic: str
    urgency: Literal["low", "medium", "high"]
    summary: str
    suggested_action: str


class Lab2ResultPayload(BaseModel):
    results: list[ReviewClassification]


class Lab2RunResponse(BaseModel):
    lab: int
    status: str
    provider: str = "openrouter"
    model: str
    dataset: str
    rows_requested: int
    rows_processed: int
    batch_size: int
    batches_processed: int
    output_file: str
    warnings: list[str] = Field(default_factory=list)
    results: list[ReviewClassification]


class Lab2SampleDataResponse(BaseModel):
    dataset: str
    total_rows: int
    sample: list[UberReviewInput]


class Lab2StatusResponse(BaseModel):
    lab: int
    name: str
    status: str
    provider: str
    dataset: str
    model: str
    configured: bool
    batching: str
    pipeline: list[str]
    available_endpoints: list[str]


class Lab3Architecture(BaseModel):
    planner: str
    tool_caller: str
    critic: str
    tools: list[str]


class Lab3StatusResponse(BaseModel):
    lab: int
    name: str
    status: str
    agent_architecture: Lab3Architecture
    security: list[str]


class Lab3DatasetItem(BaseModel):
    name: str
    path: str
    type: str


class Lab3DatasetsResponse(BaseModel):
    datasets: list[Lab3DatasetItem]


class RoleMatch(BaseModel):
    column: str | None
    confidence: float
    reason: str


class Lab3ColumnMapping(BaseModel):
    roles: dict[str, RoleMatch]
    numeric_columns: list[str] = Field(default_factory=list)
    categorical_columns: list[str] = Field(default_factory=list)


class Lab3ProfileResponse(BaseModel):
    dataset_name: str
    total_rows: int
    total_columns: int
    columns: list[str]
    dtypes: dict[str, str]
    missing_values: dict[str, int]
    sample_values: dict[str, list[str]]
    numeric_columns: list[str]
    text_like_columns: list[str]
    date_like_columns: list[str]
    categorical_columns: list[str]
    column_mapping: Lab3ColumnMapping


class Lab3MapColumnsRequest(BaseModel):
    dataset_name: str
    user_overrides: dict[str, str | None] = Field(default_factory=dict)


class Lab3RunToolRequest(BaseModel):
    dataset_name: str
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    column_overrides: dict[str, str | None] = Field(default_factory=dict)


class Lab3AskRequest(BaseModel):
    dataset_name: str
    question: str
    column_overrides: dict[str, str | None] = Field(default_factory=dict)
    max_tool_calls: int = Field(default=6, ge=1, le=20)
    use_critic: bool = False
    analysis_mode: Literal["fast", "balanced", "full", "code_interpreter"] = "code_interpreter"
    max_code_steps: int | None = Field(default=None, ge=1, le=1000)
    session_id: str | None = None
    chat_id: str | None = None
    message_id: str | None = None
    include_history: bool = True
    reset_session: bool = False


class Lab3AskResponse(BaseModel):
    lab: int
    status: str
    dataset: str
    question: str
    analysis_mode: Literal["fast", "balanced", "full", "code_interpreter"]
    provider: str = "openrouter"
    model: str
    llm_calls_count: int
    elapsed_seconds: float
    warnings: list[str] = Field(default_factory=list)
    session_id: str
    history_length: int = 0
    conversation_summary: str = ""
    column_mapping: dict[str, Any]
    planner_output: dict[str, Any]
    planner_warnings: list[str] = Field(default_factory=list)
    executed_tools: list[dict[str, Any]] = Field(default_factory=list)
    final_answer: str
    critic_review: dict[str, Any] | None = None
    code_steps: list[dict[str, Any]] = Field(default_factory=list)
    generated_files: list[dict[str, Any]] = Field(default_factory=list)
    code_interpreter_trace: str | None = None
    output_files: dict[str, str] | None = None
    successful_executions_count: int = 0
    debug_warnings: list[str] = Field(default_factory=list)
    raw_messages: list[dict[str, Any]] = Field(default_factory=list)


class Lab3ResetSessionRequest(BaseModel):
    session_id: str


class OllamaGenerateResponse(BaseModel):
    model: str
    response: str
    done: bool
    raw: dict[str, Any]


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


class DatasetsResponse(BaseModel):
    items: list[dict[str, Any]]


class ArtifactRegisterRequest(BaseModel):
    kind: str
    title: str
    path: str
    chat_id: str | None = None
    message_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactsResponse(BaseModel):
    items: list[dict[str, Any]]
