from __future__ import annotations

import ast
import logging
import mimetypes
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.dataset_resolver import resolve_dataset_for_user
from app.services.sandbox_runner import DockerSandboxRunner, LocalSubprocessRunner, SandboxLimits

SOFT_BLOCK_TOKENS = [
    "pip install",
    "conda install",
    "apt-get",
]
logger = logging.getLogger(__name__)


def _soft_block_reason(code: str) -> str | None:
    low = code.lower()
    for token in SOFT_BLOCK_TOKENS:
        if token in low:
            return f"Blocked token: {token}. Installing packages at runtime is not allowed."

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "pip":
                    return "Blocked import: pip"
    return None


def _dataset_path(dataset_name: str) -> Path:
    return resolve_dataset_for_user(dataset_name, None).path


def _collect_files(run_dir: Path, limits: SandboxLimits) -> list[dict[str, Any]]:
    allowed_suffixes = {".png", ".jpg", ".jpeg", ".webp", ".csv", ".xlsx", ".xls", ".json", ".html", ".md"}
    files: list[dict[str, Any]] = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name in {"script.py"}:
            continue
        if "__pycache__" in path.parts:
            continue
        if path.suffix.lower() not in allowed_suffixes:
            continue
        size = path.stat().st_size
        if size > limits.max_file_size:
            path.unlink(missing_ok=True)
            continue
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        files.append({"name": path.name, "path": str(path), "size": int(size), "mime_type": mime_type})
        if len(files) >= limits.max_files:
            break
    return files


def prepare_sandbox_work_dir(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        code_runs_root = (Path(settings.outputs_dir) / "lab3" / "code_runs").resolve()
        run_dir_resolved = run_dir.resolve()
        if code_runs_root in run_dir_resolved.parents:
            run_dir.chmod(0o777)
    except Exception:
        logger.debug("Could not chmod run_dir=%s", str(run_dir), exc_info=True)


def _build_script(
    code: str,
    run_dir: Path,
    *,
    dataset_inside_container: bool,
    dataset_path_local: Path | None,
    dataset_name: str | None,
    column_mapping: dict[str, Any] | None,
    profile: dict[str, Any] | None,
) -> str:
    if dataset_inside_container:
        dataset_path_line = "dataset_path = Path('/input/dataset.csv')\n"
        output_dir_line = "output_dir = Path('/work')\n"
    elif dataset_path_local is not None:
        dataset_path_line = f"dataset_path = Path(r'''{str(dataset_path_local)}''')\n"
        output_dir_line = f"output_dir = Path(r'''{str(run_dir)}''')\n"
    else:
        dataset_path_line = "dataset_path = None\n"
        output_dir_line = f"output_dir = Path(r'''{str(run_dir)}''')\n"

    dataset_loader = "df = pd.DataFrame()\n"
    if dataset_name and dataset_path_local and dataset_path_local.exists() and dataset_path_local.is_file():
        suffix = dataset_path_local.suffix.lower()
        dataset_loader = "df = pd.read_csv(dataset_path)\n" if suffix == ".csv" else "df = pd.read_excel(dataset_path)\n"

    return (
        "import pandas as pd\n"
        "import numpy as np\n"
        "import scipy\n"
        "import seaborn as sns\n"
        "import matplotlib\n"
        "matplotlib.use('Agg')\n"
        "from matplotlib import pyplot as plt\n"
        "from sklearn.model_selection import train_test_split\n"
        "from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score, accuracy_score\n"
        "from sklearn.linear_model import LinearRegression, LogisticRegression\n"
        "from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier\n"
        "import json\n"
        "import math\n"
        "import statistics\n"
        "import re\n"
        "from collections import Counter, defaultdict\n"
        "from datetime import datetime\n"
        "from pathlib import Path\n"
        f"{dataset_path_line}"
        f"{output_dir_line}"
        f"dataset_name = {dataset_name!r}\n"
        f"column_mapping = {repr(column_mapping or {})}\n"
        f"profile = {repr(profile or {})}\n"
        "output_dir.mkdir(parents=True, exist_ok=True)\n"
        "_auto_plot_idx = 0\n"
        "def _safe_show(*args, **kwargs):\n"
        "    global _auto_plot_idx\n"
        "    nums = list(plt.get_fignums())\n"
        "    if nums:\n"
        "        for num in nums:\n"
        "            fig = plt.figure(num)\n"
        "            fig.savefig(output_dir / f'plot_{_auto_plot_idx}.png', dpi=150, bbox_inches='tight')\n"
        "            _auto_plot_idx += 1\n"
        "    plt.close('all')\n"
        "plt.show = _safe_show\n"
        f"{dataset_loader}"
        "\n"
        f"{code}\n"
    )


def _build_runner() -> tuple[Any, bool]:
    mode = str(getattr(settings, "sandbox_runner_mode", "docker")).strip().lower()
    image = str(getattr(settings, "sandbox_docker_image", "llm-data-analytics-sandbox:latest")).strip()
    if mode == "local":
        return LocalSubprocessRunner(), False
    return DockerSandboxRunner(image=image), True


def _run(
    code: str,
    *,
    run_id: str,
    dataset_name: str | None,
    user_id: str | None,
    step: int | None,
    column_mapping: dict[str, Any] | None,
    profile: dict[str, Any] | None,
) -> dict[str, Any]:
    reason = _soft_block_reason(code)
    if reason:
        return {"status": "blocked", "reason": reason}

    run_dir = Path(settings.outputs_dir) / "lab3" / "code_runs" / run_id
    prepare_sandbox_work_dir(run_dir)

    dataset_path = resolve_dataset_for_user(dataset_name, user_id).path if dataset_name else None
    timeout_seconds = int(getattr(settings, "lab3_code_exec_timeout_seconds", 15))
    limits = SandboxLimits(timeout_seconds=timeout_seconds)

    runner, in_docker = _build_runner()
    script = _build_script(
        code,
        run_dir,
        dataset_inside_container=in_docker,
        dataset_path_local=dataset_path,
        dataset_name=dataset_name,
        column_mapping=column_mapping,
        profile=profile,
    )
    script_path = run_dir / "script.py"
    script_path.write_text(script, encoding="utf-8")
    try:
        script_path.chmod(0o644)
    except Exception:
        logger.debug("Could not chmod script_path=%s", str(script_path), exc_info=True)

    logger.info("CODE_EXEC_START run_id=%s mode=%s dataset=%s", run_id, runner.__class__.__name__, dataset_name or "-")
    res = runner.run(
        script_path=script_path,
        work_dir=run_dir,
        dataset_path=dataset_path,
        limits=limits,
        run_id=run_id,
        step=step,
    )

    files = _collect_files(run_dir, limits)
    out = {
        "status": "error" if res.status == "timeout" else res.status,
        "stdout": res.stdout,
        "stderr": res.stderr,
        "files": files,
        "elapsed_seconds": res.elapsed_seconds,
    }
    if res.reason:
        out["reason"] = res.reason
    logger.info("CODE_EXEC_DONE run_id=%s status=%s files=%s", run_id, out["status"], len(files))
    return out


def execute_python_code(
    code: str,
    dataset_name: str,
    run_id: str,
    *,
    user_id: str | None = None,
    step: int | None = None,
    column_mapping: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _run(
        code,
        run_id=run_id,
        dataset_name=dataset_name,
        user_id=user_id,
        step=step,
        column_mapping=column_mapping,
        profile=profile,
    )


def execute_python_code_general(
    code: str,
    run_id: str,
    *,
    dataset_name: str | None = None,
    user_id: str | None = None,
    step: int | None = None,
    column_mapping: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _run(
        code,
        run_id=run_id,
        dataset_name=dataset_name,
        user_id=user_id,
        step=step,
        column_mapping=column_mapping,
        profile=profile,
    )
