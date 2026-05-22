from typing import Any, Literal

from pydantic import BaseModel, Field


class McpToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    call_id: str | None = None


class McpToolResult(BaseModel):
    call_id: str | None = None
    name: str
    status: Literal["success", "error"]
    content: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class RunPythonArgs(BaseModel):
    code: str
    dataset_path: str | None = None
    run_id: str | None = None
