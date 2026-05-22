from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.llm.client import LlmClient, LlmClientError
from app.llm.models import LlmMessage
from app.mcp.server import McpToolServer

router = APIRouter(tags=["dev-llm"])


class DevLlmChatRequest(BaseModel):
    prompt: str
    include_run_python_tool: bool = False
    system_prompt: str | None = None


class DevLlmChatResponse(BaseModel):
    content: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


@router.post("/dev/llm/chat", response_model=DevLlmChatResponse)
def dev_llm_chat(payload: DevLlmChatRequest) -> DevLlmChatResponse:
    messages: list[LlmMessage] = []
    if payload.system_prompt:
        messages.append(LlmMessage(role="system", content=payload.system_prompt))
    messages.append(LlmMessage(role="user", content=payload.prompt))

    tools = None
    if payload.include_run_python_tool:
        tools = McpToolServer().list_tools()

    client = LlmClient()
    try:
        result = client.chat(messages=messages, tools=tools)
    except LlmClientError as exc:
        return DevLlmChatResponse(content="", tool_calls=[], raw={"error": str(exc)})

    return DevLlmChatResponse(
        content=result.content,
        tool_calls=[tc.model_dump() for tc in result.tool_calls],
        raw=result.raw,
    )
