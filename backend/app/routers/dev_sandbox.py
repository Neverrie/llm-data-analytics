import uuid
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings
from app.sandbox.factory import get_sandbox_runner
from app.sandbox.models import SandboxLimits, SandboxResult, SandboxRunRequest

router = APIRouter(tags=["dev-sandbox"])


class DevSandboxRunBody(BaseModel):
    code: str


@router.post("/dev/sandbox/run", response_model=SandboxResult)
def dev_sandbox_run(payload: DevSandboxRunBody) -> SandboxResult:
    run_id = str(uuid.uuid4())
    work_dir = Path(settings.outputs_dir) / "sandbox_runs" / run_id

    request = SandboxRunRequest(
        code=payload.code,
        work_dir=work_dir,
        dataset_path=None,
        limits=SandboxLimits(),
    )
    runner = get_sandbox_runner()
    return runner.run(request)
