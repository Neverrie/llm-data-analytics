from __future__ import annotations

from typing import Any

from app.services.lab2_service import Lab2PipelineError

ALLOWED_TOOLS = {
    "get_dataset_schema",
    "get_sample_rows",
    "get_missing_values_report",
    "get_duplicate_text_report",
    "describe_numeric_columns",
    "describe_rating",
    "get_rating_distribution",
    "get_low_rating_rows",
    "get_high_rating_rows",
    "compare_low_high_rating_rows",
    "get_text_length_stats",
    "extract_top_keywords",
    "search_rows_by_keyword",
    "cluster_texts_by_topic_simple",
    "get_rows_by_month",
    "get_average_rating_by_month",
    "get_rows_by_version",
    "get_average_rating_by_version",
    "find_problematic_versions",
    "get_reply_rate",
    "get_reply_rate_by_rating",
    "find_unanswered_critical_rows",
    "detect_text_prompt_injection_patterns",
    "explain_prompt_injection_protection",
    "create_rating_distribution_chart",
    "create_rows_by_month_chart",
    "generate_markdown_report",
    "export_lab3_result_json",
    "get_available_tools",
}


def get_sensitive_columns_from_mapping(column_mapping: dict[str, Any]) -> list[str]:
    roles = column_mapping.get("roles", {})
    sensitive = []
    for role_name in ("username_column", "image_column"):
        role = roles.get(role_name) or {}
        column_name = role.get("column")
        if isinstance(column_name, str) and column_name:
            sensitive.append(column_name)
    return sensitive


def sanitize_rows_for_llm(rows: list[dict[str, Any]], column_mapping: dict[str, Any]) -> list[dict[str, Any]]:
    sensitive = set(get_sensitive_columns_from_mapping(column_mapping))
    cleaned_rows: list[dict[str, Any]] = []
    for row in rows:
        cleaned_rows.append({key: value for key, value in row.items() if key not in sensitive})
    return cleaned_rows


def validate_tool_call(tool_call: dict[str, Any]) -> None:
    tool_name = tool_call.get("tool")
    if not isinstance(tool_name, str) or not tool_name:
        raise Lab2PipelineError("Tool call must contain non-empty 'tool'.")
    if tool_name not in ALLOWED_TOOLS:
        raise Lab2PipelineError(f"Tool '{tool_name}' is not in allowlist.")
    arguments = tool_call.get("arguments", {})
    if not isinstance(arguments, dict):
        raise Lab2PipelineError("Tool call 'arguments' must be an object.")
