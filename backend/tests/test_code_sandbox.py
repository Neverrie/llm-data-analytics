from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.config import settings
from app.services.code_sandbox import execute_python_code


@pytest.fixture
def sandbox_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    datasets_dir = tmp_path / "datasets"
    outputs_dir = tmp_path / "outputs"
    datasets_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "datasets_dir", str(datasets_dir))
    monkeypatch.setattr(settings, "outputs_dir", str(outputs_dir))

    frame = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    frame.to_csv(datasets_dir / "demo.csv", index=False)
    return datasets_dir


def test_code_sandbox_blocks_forbidden_import(sandbox_paths: Path) -> None:
    result = execute_python_code("import os\nprint('x')", "demo.csv", "run1")
    assert result["status"] == "blocked"
    assert "Forbidden import" in result["reason"]


def test_code_sandbox_executes_safe_pandas_code(sandbox_paths: Path) -> None:
    result = execute_python_code("print(df.shape)", "demo.csv", "run2")
    assert result["status"] == "success"
    assert "(3, 2)" in result["stdout"]


def test_code_sandbox_timeout(sandbox_paths: Path) -> None:
    result = execute_python_code("while True:\n    pass", "demo.csv", "run3")
    assert result["status"] == "error"
    assert "timeout" in result["stderr"].lower()
