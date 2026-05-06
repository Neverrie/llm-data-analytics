from __future__ import annotations

import ast
import json
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import settings

FORBIDDEN_IMPORTS = {
    "os",
    "subprocess",
    "socket",
    "requests",
    "urllib",
    "shutil",
    "sys",
    "pathlib",
}
FORBIDDEN_TOKENS = [
    "open(",
    "exec(",
    "eval(",
    "__import__",
    "input(",
    "compile(",
    "globals(",
    "locals(",
    "get_ipython",
    ".system(",
    "!pip",
    "pip install",
    "conda install",
    "pd.read_csv(",
    "pd.read_excel(",
    "read_csv(",
    "read_excel(",
    "listdir",
    "walk(",
    "remove(",
    "unlink(",
    "rmdir(",
    "mkdir(",
    "makedirs(",
    "pathlib",
    "powershell",
    "bash -c",
    "cmd /c",
]
MAX_STDIO = 12000
MAX_FILES = 20
MAX_FILE_SIZE = 5 * 1024 * 1024
logger = logging.getLogger(__name__)


def _block_reason(code: str) -> str | None:
    low = code.lower()
    for token in FORBIDDEN_TOKENS:
        if token in low:
            if token in {"pd.read_csv(", "pd.read_excel(", "read_csv(", "read_excel("}:
                return f"Forbidden token: {token}. The dataframe is already available as df."
            return f"Forbidden token: {token}"

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in FORBIDDEN_IMPORTS:
                    return f"Forbidden import: {root}"
        if isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root in FORBIDDEN_IMPORTS:
                    return f"Forbidden import: {root}"
    return None


def _dataset_path(dataset_name: str) -> Path:
    path = (Path(settings.datasets_dir) / dataset_name).resolve()
    base = Path(settings.datasets_dir).resolve()
    if base not in path.parents and path != base:
        raise ValueError("Invalid dataset path")
    return path


def execute_python_code(
    code: str,
    dataset_name: str,
    run_id: str,
    *,
    column_mapping: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reason = _block_reason(code)
    if reason:
        return {"status": "blocked", "reason": reason}

    run_dir = Path(settings.outputs_dir) / "lab3" / "code_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = _dataset_path(dataset_name)

    suffix = dataset_path.suffix.lower()
    loader = "pd.read_csv(dataset_path)" if suffix == ".csv" else "pd.read_excel(dataset_path)"

    script = (
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
        f"dataset_path = Path(r'''{str(dataset_path)}''')\n"
        f"output_dir = Path(r'''{str(run_dir)}''')\n"
        f"dataset_name = {dataset_name!r}\n"
        f"column_mapping = {repr(column_mapping or {})}\n"
        f"profile = {repr(profile or {})}\n"
        "output_dir.mkdir(parents=True, exist_ok=True)\n"
        "_auto_plot_idx = 0\n"
        "_orig_show = plt.show\n"
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
        f"df = {loader}\n"
        "\n"
        f"{code}\n"
    )

    script_path = run_dir / "script.py"
    script_path.write_text(script, encoding="utf-8")

    started = time.perf_counter()
    timeout_seconds = int(getattr(settings, "lab3_code_exec_timeout_seconds", 15))
    logger.info("LAB3_CODE_EXEC_START step=%s code_chars=%s", run_id, len(code))
    try:
        proc = subprocess.run(
            [sys.executable, "-I", str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=run_dir,
        )
        status = "success" if proc.returncode == 0 else "error"
        stdout = (proc.stdout or "")[:MAX_STDIO]
        stderr = (proc.stderr or "")[:MAX_STDIO]
    except subprocess.TimeoutExpired as exc:
        logger.error("LAB3_CODE_EXEC_DONE step=%s status=timeout elapsed=%.3f", run_id, time.perf_counter() - started)
        return {
            "status": "error",
            "stdout": (exc.stdout or "")[:MAX_STDIO],
            "stderr": f"Execution timeout exceeded {timeout_seconds} seconds.",
            "files": [],
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }

    files: list[dict[str, Any]] = []
    for path in sorted(run_dir.iterdir()):
        if path.name in {"script.py"}:
            continue
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size > MAX_FILE_SIZE:
            path.unlink(missing_ok=True)
            continue
        files.append({"name": path.name, "path": str(path), "size": int(size)})
        if len(files) >= MAX_FILES:
            break

    result = {
        "status": status,
        "stdout": stdout,
        "stderr": stderr,
        "files": files,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    logger.info(
        "LAB3_CODE_EXEC_DONE step=%s status=%s elapsed=%.3f stdout_len=%s stderr_len=%s",
        run_id,
        status,
        result["elapsed_seconds"],
        len(stdout),
        len(stderr),
    )
    return result


def execute_python_code_general(
    code: str,
    run_id: str,
    *,
    dataset_name: str | None = None,
    column_mapping: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reason = _block_reason(code)
    if reason:
        return {"status": "blocked", "reason": reason}

    run_dir = Path(settings.outputs_dir) / "lab3" / "code_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    dataset_loader = "df = pd.DataFrame()\n"
    dataset_path_line = "dataset_path = None\n"
    dataset_hint_line = ""
    if dataset_name:
        try:
            dataset_path = _dataset_path(dataset_name)
            if dataset_path.exists() and dataset_path.is_file():
                suffix = dataset_path.suffix.lower()
                loader = "pd.read_csv(dataset_path)" if suffix == ".csv" else "pd.read_excel(dataset_path)"
                dataset_path_line = f"dataset_path = Path(r'''{str(dataset_path)}''')\n"
                dataset_loader = f"df = {loader}\n"
            else:
                dataset_hint_line = f"print({('WARN: dataset file not found for ' + repr(dataset_name) + ', fallback to empty df')!r})\n"
        except Exception:
            dataset_hint_line = f"print({('WARN: invalid dataset path for ' + repr(dataset_name) + ', fallback to empty df')!r})\n"

    script = (
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
        f"output_dir = Path(r'''{str(run_dir)}''')\n"
        f"dataset_name = {dataset_name!r}\n"
        f"column_mapping = {repr(column_mapping or {})}\n"
        f"profile = {repr(profile or {})}\n"
        "output_dir.mkdir(parents=True, exist_ok=True)\n"
        "_auto_plot_idx = 0\n"
        "_orig_show = plt.show\n"
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
        f"{dataset_hint_line}"
        f"{dataset_loader}"
        "\n"
        f"{code}\n"
    )

    script_path = run_dir / "script.py"
    script_path.write_text(script, encoding="utf-8")

    started = time.perf_counter()
    timeout_seconds = int(getattr(settings, "lab3_code_exec_timeout_seconds", 15))
    logger.info("GEN_CODE_EXEC_START run_id=%s dataset=%s code_chars=%s", run_id, dataset_name or "-", len(code))
    try:
        proc = subprocess.run(
            [sys.executable, "-I", str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=run_dir,
        )
        status = "success" if proc.returncode == 0 else "error"
        stdout = (proc.stdout or "")[:MAX_STDIO]
        stderr = (proc.stderr or "")[:MAX_STDIO]
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "error",
            "stdout": (exc.stdout or "")[:MAX_STDIO],
            "stderr": f"Execution timeout exceeded {timeout_seconds} seconds.",
            "files": [],
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }

    files: list[dict[str, Any]] = []
    for path in sorted(run_dir.iterdir()):
        if path.name in {"script.py"}:
            continue
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size > MAX_FILE_SIZE:
            path.unlink(missing_ok=True)
            continue
        files.append({"name": path.name, "path": str(path), "size": int(size)})
        if len(files) >= MAX_FILES:
            break

    return {
        "status": status,
        "stdout": stdout,
        "stderr": stderr,
        "files": files,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
