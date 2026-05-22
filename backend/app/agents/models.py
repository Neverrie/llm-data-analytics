from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentStep(BaseModel):
    step_index: int
    type: Literal["llm", "tool"]
    content: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    final_answer: str
    steps: list[AgentStep] = Field(default_factory=list)
    files: list[dict[str, Any]] = Field(default_factory=list)
    status: Literal["success", "error", "max_steps", "contract_error", "cancelled"]
