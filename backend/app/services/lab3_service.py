from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.lab2_service import Lab2PipelineError
from app.services.lab3_agent import run_agent
from app.services.lab3_column_mapper import (
    get_effective_column_mapping,
    list_datasets,
    load_dataset,
    profile_dataset,
)
from app.services.lab3_tools import TOOL_METADATA, execute_tool


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
            "planner/tool-caller/critic chain",
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
    _, mapping = await get_effective_column_mapping(dataset_name, user_overrides={})
    profile["column_mapping"] = mapping.model_dump()
    return profile


async def map_columns(dataset_name: str, user_overrides: dict[str, str | None]) -> dict[str, Any]:
    profile, mapping = await get_effective_column_mapping(dataset_name, user_overrides=user_overrides)
    return {"dataset_name": dataset_name, "profile_summary": {"rows": profile["total_rows"], "columns": profile["columns"]}, "column_mapping": mapping.model_dump()}


def get_tools() -> dict[str, Any]:
    tools = [{"tool": name, **meta} for name, meta in TOOL_METADATA.items()]
    return {"tools": tools}


async def run_tool(dataset_name: str, tool: str, arguments: dict[str, Any], column_overrides: dict[str, str | None]) -> dict[str, Any]:
    _, mapping = await get_effective_column_mapping(dataset_name, user_overrides=column_overrides)
    return execute_tool(dataset_name, tool, mapping.model_dump(), arguments)


async def ask_agent(
    dataset_name: str,
    question: str,
    column_overrides: dict[str, str | None],
    max_tool_calls: int,
    use_critic: bool,
) -> dict[str, Any]:
    return await run_agent(
        dataset_name=dataset_name,
        question=question,
        column_overrides=column_overrides,
        max_tool_calls=max_tool_calls,
        use_critic=use_critic,
    )


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
