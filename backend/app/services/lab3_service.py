from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import UploadFile

from app.config import settings
from app.services.lab2_service import Lab2PipelineError
from app.services.lab3_agent import run_agent
from app.services.lab3_column_mapper import get_effective_column_mapping, list_datasets, load_dataset, profile_dataset
from app.services.lab3_session import load_session, reset_session
from app.services.lab3_tools import TOOL_METADATA, execute_tool

MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024
_ALLOWED_UPLOAD_SUFFIXES = {".csv": "csv", ".xlsx": "xlsx", ".xls": "xls"}
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def get_lab3_status() -> dict[str, Any]:
    return {
        "lab": 3,
        "status": "ready",
        "models": {
            "planner_model": settings.lab3_planner_model,
            "tool_caller_model": settings.lab3_tool_caller_model,
            "critic_model": settings.lab3_critic_model,
        },
        "features": [
            "semantic column mapping",
            "allowlisted analytical tools",
            "analysis modes: fast/balanced/full",
            "dataset upload (csv/xlsx)",
            "markdown and json report export",
            "agent trace logging",
        ],
        "safety_rules": [
            "CSV content is treated as data, not instructions",
            "Only allowlisted tools can be called",
            "No arbitrary code execution from LLM output",
            "Tool arguments are validated",
            "Sensitive columns are excluded from LLM context",
        ],
    }


def get_datasets() -> dict[str, Any]:
    return {"datasets": list_datasets()}


async def get_profile(dataset_name: str) -> dict[str, Any]:
    profile = profile_dataset(dataset_name)
    _, mapping, _ = await get_effective_column_mapping(dataset_name, user_overrides={}, use_llm_assist=False)
    profile["column_mapping"] = mapping.model_dump()
    return profile


async def map_columns(dataset_name: str, user_overrides: dict[str, str | None]) -> dict[str, Any]:
    profile, mapping, _ = await get_effective_column_mapping(dataset_name, user_overrides=user_overrides, use_llm_assist=False)
    return {
        "dataset_name": dataset_name,
        "profile_summary": {"rows": profile["total_rows"], "columns": profile["columns"]},
        "column_mapping": mapping.model_dump(),
    }


def get_tools() -> dict[str, Any]:
    tools = [{"tool": name, **meta} for name, meta in TOOL_METADATA.items()]
    return {"tools": tools}


async def run_tool(dataset_name: str, tool: str, arguments: dict[str, Any], column_overrides: dict[str, str | None]) -> dict[str, Any]:
    _, mapping, _ = await get_effective_column_mapping(dataset_name, user_overrides=column_overrides, use_llm_assist=False)
    return execute_tool(dataset_name, tool, mapping.model_dump(), arguments)


async def ask_agent(
    dataset_name: str,
    question: str,
    column_overrides: dict[str, str | None],
    max_tool_calls: int,
    use_critic: bool,
    analysis_mode: str,
    session_id: str | None = None,
    include_history: bool = True,
    reset_session_flag: bool = False,
) -> dict[str, Any]:
    return await run_agent(
        dataset_name=dataset_name,
        question=question,
        column_overrides=column_overrides,
        max_tool_calls=max_tool_calls,
        use_critic=use_critic,
        analysis_mode=analysis_mode,
        session_id=session_id,
        include_history=include_history,
        reset_session=reset_session_flag,
    )


def get_session_state(session_id: str) -> dict[str, Any]:
    state = load_session(session_id)
    if state is None:
        raise Lab2PipelineError("Session not found.", status_code=404)
    return {
        "session_id": state.get("session_id", session_id),
        "dataset_name": state.get("dataset_name"),
        "created_at": state.get("created_at"),
        "updated_at": state.get("updated_at"),
        "history_length": len(state.get("turns", [])),
        "conversation_summary": state.get("conversation_summary", ""),
        "turns": state.get("turns", []),
    }


def clear_session(session_id: str) -> dict[str, str]:
    reset_session(session_id)
    return {"status": "success"}


def get_last_result() -> dict[str, Any]:
    output_path = Path(settings.outputs_dir) / "lab3" / "lab3_result.json"
    if not output_path.exists():
        trace_path = Path(settings.outputs_dir) / "lab3" / "agent_trace.json"
        if not trace_path.exists():
            raise Lab2PipelineError("No Lab 3 result found. Run /api/lab3/ask first.", status_code=404)
        return json.loads(trace_path.read_text(encoding="utf-8"))
    return json.loads(output_path.read_text(encoding="utf-8"))


def get_report_path() -> Path:
    report_path = Path(settings.outputs_dir) / "lab3" / "lab3_report.md"
    if not report_path.exists():
        raise Lab2PipelineError("Lab 3 report does not exist yet. Run /api/lab3/ask first.", status_code=404)
    return report_path


def _safe_filename(name: str) -> str:
    base = Path(name).name.replace(" ", "_")
    safe = _SAFE_FILENAME_RE.sub("_", base)
    safe = safe.strip("._") or "dataset"
    return safe


async def upload_dataset(file: UploadFile) -> dict[str, Any]:
    original_name = file.filename or "dataset.csv"
    safe_name = _safe_filename(original_name)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in _ALLOWED_UPLOAD_SUFFIXES:
        raise Lab2PipelineError("Unsupported file extension. Allowed: .csv, .xlsx, .xls", status_code=400)

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise Lab2PipelineError("File is too large. Max size is 20 MB.", status_code=400)

    uploads_dir = Path(settings.datasets_dir) / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    output_name = safe_name
    output_path = uploads_dir / output_name
    if output_path.exists():
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_name = f"{Path(safe_name).stem}_{timestamp}{suffix}"
        output_path = uploads_dir / output_name

    output_path.write_bytes(content)

    try:
        if suffix == ".csv":
            frame = pd.read_csv(output_path)
        else:
            frame = pd.read_excel(output_path)
    except Exception as exc:  # pragma: no cover
        output_path.unlink(missing_ok=True)
        raise Lab2PipelineError(f"Uploaded file cannot be parsed: {exc}", status_code=400) from exc

    return {
        "status": "success",
        "dataset": {
            "name": f"uploads/{output_name}",
            "type": _ALLOWED_UPLOAD_SUFFIXES[suffix],
            "rows": int(len(frame)),
            "columns": int(len(frame.columns)),
        },
    }
