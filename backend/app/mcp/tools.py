import uuid
from pathlib import Path

from app.config import settings
from app.mcp.models import McpToolResult, RunPythonArgs
from app.sandbox.factory import get_sandbox_runner
from app.sandbox.models import SandboxLimits, SandboxRunRequest
from app.sandbox.runner import SandboxRunner


class SandboxTools:
    def __init__(self, runner: SandboxRunner | None = None):
        self.runner = runner or get_sandbox_runner()

    def _is_allowed_dataset_path(self, dataset_path: Path) -> bool:
        roots = [Path(settings.datasets_dir), Path(settings.outputs_dir)]
        resolved = dataset_path.resolve()
        for root in roots:
            try:
                resolved.relative_to(root.resolve())
                return True
            except Exception:
                continue
        return False

    def run_python(self, args: RunPythonArgs) -> McpToolResult:
        run_id = args.run_id or str(uuid.uuid4())
        work_dir = Path(settings.outputs_dir) / "mcp_runs" / run_id

        dataset_path: Path | None = None
        if args.dataset_path:
            candidate = Path(args.dataset_path)
            if not candidate.exists():
                # Uploaded files are stored as "<uuid>_<original_name>".
                # If caller provides "/datasets/<original_name>", try to resolve by suffix match.
                try:
                    datasets_root = Path(settings.datasets_dir)
                    if candidate.parent == datasets_root and candidate.name:
                        matches = sorted(datasets_root.glob(f"*_{candidate.name}"))
                        if matches:
                            candidate = matches[-1]
                except Exception:
                    pass
            if not candidate.exists():
                return McpToolResult(
                    name="run_python",
                    status="error",
                    content={"run_id": run_id},
                    error=f"dataset_path does not exist: {args.dataset_path}",
                )
            if not self._is_allowed_dataset_path(candidate):
                return McpToolResult(
                    name="run_python",
                    status="error",
                    content={"run_id": run_id},
                    error="dataset_path is outside allowed directories",
                )
            dataset_path = candidate

        result = self.runner.run(
            SandboxRunRequest(
                code=args.code,
                work_dir=work_dir,
                dataset_path=dataset_path,
                limits=SandboxLimits(),
            )
        )

        content = {
            "sandbox_status": result.status,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "files": [f.model_dump() for f in result.files],
            "elapsed_seconds": result.elapsed_seconds,
            "exit_code": result.exit_code,
            "run_id": run_id,
        }

        if result.status == "success":
            return McpToolResult(name="run_python", status="success", content=content)

        return McpToolResult(
            name="run_python",
            status="error",
            content=content,
            error=(result.stderr or "Sandbox execution failed")[:1000],
        )
