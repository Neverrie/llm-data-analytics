from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class SandboxLimits(BaseModel):
    timeout_seconds: int = 60
    memory: str = "512m"
    cpus: float = 1.0
    pids_limit: int = 128
    max_output_chars: int = 20000


class SandboxFile(BaseModel):
    path: str
    filename: str
    size_bytes: int
    mime_type: str | None = None


class SandboxResult(BaseModel):
    status: Literal["success", "error", "timeout"]
    stdout: str
    stderr: str
    files: list[SandboxFile] = Field(default_factory=list)
    elapsed_seconds: float
    exit_code: int | None = None


class SandboxRunRequest(BaseModel):
    code: str
    work_dir: Path
    dataset_path: Path | None = None
    limits: SandboxLimits = Field(default_factory=SandboxLimits)
