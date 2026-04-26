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
    limit: int = Field(default=10, ge=1, le=100)
    min_score: int | None = Field(default=None, ge=1, le=5)
    max_score: int | None = Field(default=None, ge=1, le=5)


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
    rows_processed: int
    output_file: str
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


class OllamaGenerateResponse(BaseModel):
    model: str
    response: str
    done: bool
    raw: dict[str, Any]
