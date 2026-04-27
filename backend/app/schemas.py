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
    limit: int = Field(default=10, ge=1)
    min_score: int | None = Field(default=None, ge=1, le=5)
    max_score: int | None = Field(default=None, ge=1, le=5)
    batch_size: int = Field(default=5, ge=1, le=20)


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
    dataset: str
    model: str
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
    analysis_mode: Literal["fast", "balanced", "full"] = "fast"


class OllamaGenerateResponse(BaseModel):
    model: str
    response: str
    done: bool
    raw: dict[str, Any]
