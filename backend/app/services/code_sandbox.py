from __future__ import annotations

import ast
import json
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
    "pip",
    "conda",
    "..",
]
MAX_STDIO = 12000
MAX_FILES = 20
MAX_FILE_SIZE = 5 * 1024 * 1024
TIMEOUT_SECONDS = 15


def _block_reason(code: str) -> str | None:
    low = code.lower()
    for token in FORBIDDEN_TOKENS:
        if token in low:
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


def execute_python_code(code: str, dataset_name: str, run_id: str) -> dict[str, Any]:
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
        "import matplotlib\n"
        "matplotlib.use('Agg')\n"
        "from matplotlib import pyplot as plt\n"
        "import json\n"
        "import math\n"
        "import statistics\n"
        "import re\n"
        "from collections import Counter, defaultdict\n"
        "from datetime import datetime\n"
        "from pathlib import Path\n"
        f"dataset_path = Path(r'''{str(dataset_path)}''')\n"
        f"output_dir = Path(r'''{str(run_dir)}''')\n"
        "output_dir.mkdir(parents=True, exist_ok=True)\n"
        f"df = {loader}\n"
        "\n"
        f"{code}\n"
    )

    script_path = run_dir / "script.py"
    script_path.write_text(script, encoding="utf-8")

    started = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, "-I", str(script_path)],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            cwd=run_dir,
        )
        status = "success" if proc.returncode == 0 else "error"
        stdout = (proc.stdout or "")[:MAX_STDIO]
        stderr = (proc.stderr or "")[:MAX_STDIO]
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "error",
            "stdout": (exc.stdout or "")[:MAX_STDIO],
            "stderr": "Execution timeout exceeded 15 seconds.",
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
