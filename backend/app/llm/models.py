from typing import Any, Literal

from pydantic import BaseModel, Field


class LlmMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None


class LlmToolCall(BaseModel):
    id: str | None = None
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class LlmResponse(BaseModel):
    content: str
    tool_calls: list[LlmToolCall] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
