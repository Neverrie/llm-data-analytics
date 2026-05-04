from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import UploadFile

from app.config import get_lab3_model, settings
from app.services.lab2_service import Lab2PipelineError
from app.services.dataset_registry import datasets_for_lab3
from app.services.lab3_agent import run_agent
from app.services.lab3_column_mapper import get_effective_column_mapping, profile_dataset
from app.services.llm_client import LLMClient
from app.services.openrouter_client import OpenRouterClient, OpenRouterClientError
from app.services.lab3_session import load_session, reset_session
from app.services.lab3_tools import TOOL_METADATA, execute_tool

MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024
_ALLOWED_UPLOAD_SUFFIXES = {".csv": "csv", ".xlsx": "xlsx", ".xls": "xls"}
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")
logger = logging.getLogger(__name__)


def get_lab3_status() -> dict[str, Any]:
    llm = LLMClient()
    return {
        "lab": 3,
        "status": "ready",
        "provider": llm.provider_name(),
        "model": get_lab3_model(),
        "openrouter_configured": bool((settings.openrouter_api_key or "").strip()),
        "default_mode": "code_interpreter",
        "orchestration": "langgraph",
        "available_modes": ["fast", "balanced", "full", "code_interpreter"],
        "models": {
            "default_model": get_lab3_model(),
        },
        "features": [
            "semantic column mapping",
            "allowlisted analytical tools",
            "analysis modes: code_interpreter/fast/balanced/full",
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
    return {"datasets": datasets_for_lab3()}


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
    max_code_steps: int | None = None,
) -> dict[str, Any]:
    llm = LLMClient()
    started = time.perf_counter()
    logger.info(
        "LAB3_ASK_START dataset=%s mode=%s provider=%s model=%s question_len=%s",
        dataset_name,
        analysis_mode,
        llm.provider_name(),
        llm.resolve_model(),
        len(question or ""),
    )
    profile = profile_dataset(dataset_name)
    logger.info(
        "LAB3_PROFILE_READY rows=%s columns=%s",
        profile.get("total_rows"),
        profile.get("total_columns"),
    )
    result = await run_agent(
        dataset_name=dataset_name,
        question=question,
        column_overrides=column_overrides,
        max_tool_calls=max_tool_calls,
        use_critic=use_critic,
        analysis_mode=analysis_mode,
        session_id=session_id,
        include_history=include_history,
        reset_session=reset_session_flag,
        max_code_steps=max_code_steps,
    )
    logger.info("LAB3_ASK_DONE elapsed=%.3f", time.perf_counter() - started)
    return result


async def debug_openrouter_ping() -> dict[str, Any]:
    llm = LLMClient()
    if llm.provider_name() != "openrouter":
        raise Lab2PipelineError("Debug endpoint is available only for openrouter provider.", status_code=400)
    started = time.perf_counter()
    client = OpenRouterClient(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        default_model=settings.openrouter_model,
    )
    try:
        payload = await client.chat(
            messages=[{"role": "user", "content": "Return JSON: {\"ok\": true}"}],
            model=llm.resolve_model(),
            temperature=0.0,
            timeout=min(settings.openrouter_timeout_seconds, 20),
        )
    except OpenRouterClientError as exc:
        raise Lab2PipelineError(str(exc), status_code=503) from exc
    return {
        "status": "success",
        "provider": "openrouter",
        "model": payload.get("model", llm.resolve_model()),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


def get_current_status() -> dict[str, Any]:
    status_path = Path(settings.outputs_dir) / "lab3" / "current_status.json"
    if not status_path.exists():
        return {"status": "idle"}
    return json.loads(status_path.read_text(encoding="utf-8"))


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


def get_generated_file_path(path: str) -> Path:
    requested = Path(path).resolve()
    allowed_roots = [
        (Path(settings.outputs_dir) / "lab3").resolve(),
    ]
    if not any(root == requested or root in requested.parents for root in allowed_roots):
        raise Lab2PipelineError("Invalid generated file path.", status_code=400)
    if not requested.exists() or not requested.is_file():
        raise Lab2PipelineError("Generated file not found.", status_code=404)
    return requested


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
