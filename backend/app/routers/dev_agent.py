from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agents.dataset_agent import run_dataset_agent
from app.agents.models import AgentResult

router = APIRouter(tags=["dev-agent"])


class DevAgentRunRequest(BaseModel):
    chat_id: str = "dev-chat"
    user_message: str
    dataset_path: str | None = None
    max_steps: int = Field(default=30, ge=1, le=30)


@router.post("/dev/agent/run", response_model=AgentResult)
def dev_agent_run(payload: DevAgentRunRequest) -> AgentResult:
    return run_dataset_agent(
        chat_id=payload.chat_id,
        user_message=payload.user_message,
        dataset_path=payload.dataset_path,
        max_steps=payload.max_steps,
    )

