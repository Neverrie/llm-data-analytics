from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import matplotlib
import pandas as pd

from app.config import settings
from app.services.lab3_column_mapper import load_dataset, profile_dataset
from app.services.lab3_security import get_sensitive_columns_from_mapping

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def _tool_result(tool: str, status: str, data: Any, warnings: list[str] | None = None) -> dict[str, Any]:
    return {"tool": tool, "status": status, "data": data, "warnings": warnings or []}


def _get_role_column(mapping: dict[str, Any], role_name: str) -> str | None:
    role = mapping.get("roles", {}).get(role_name)
    if isinstance(role, dict):
        col = role.get("column")
        return col if isinstance(col, str) and col else None
    return None


def _safe_columns(frame: pd.DataFrame, mapping: dict[str, Any]) -> list[str]:
    sensitive = set(get_sensitive_columns_from_mapping(mapping))
    return [column for column in frame.columns if column not in sensitive]


def _serialize_rows(frame: pd.DataFrame, columns: list[str], limit: int = 20) -> list[dict[str, Any]]:
    rows = frame[columns].head(limit).where(pd.notna(frame[columns].head(limit)), None).to_dict(orient="records")
    return rows


def get_dataset_schema(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = arguments
    profile = {
        "rows": int(len(frame)),
        "columns": [str(column) for column in frame.columns.tolist()],
        "dtypes": {column: str(dtype) for column, dtype in frame.dtypes.items()},
        "missing_values": {column: int(frame[column].isna().sum()) for column in frame.columns},
        "inferred_roles": mapping.get("roles", {}),
    }
    return _tool_result("get_dataset_schema", "success", profile)


def get_sample_rows(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    limit = int(arguments.get("limit", 10))
    columns = _safe_columns(frame, mapping)
    return _tool_result("get_sample_rows", "success", {"rows": _serialize_rows(frame, columns, limit=limit)})


def get_missing_values_report(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = mapping, arguments
    data = {column: int(frame[column].isna().sum()) for column in frame.columns}
    return _tool_result("get_missing_values_report", "success", data)


def get_duplicate_text_report(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = arguments
    text_column = _get_role_column(mapping, "text_column")
    if not text_column:
        return _tool_result("get_duplicate_text_report", "warning", {}, ["text column not detected"])
    duplicates = frame[frame[text_column].duplicated(keep=False) & frame[text_column].notna()]
    sample = duplicates[[text_column]].head(10).astype(str).to_dict(orient="records")
    return _tool_result(
        "get_duplicate_text_report",
        "success",
        {"duplicates_count": int(len(duplicates)), "sample_duplicates": sample},
    )


def describe_numeric_columns(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = mapping, arguments
    numeric = frame.select_dtypes(include=["number"])
    if numeric.empty:
        return _tool_result("describe_numeric_columns", "warning", {}, ["no numeric columns detected"])
    return _tool_result("describe_numeric_columns", "success", numeric.describe().to_dict())


def describe_rating(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = arguments
    rating_column = _get_role_column(mapping, "rating_column")
    if not rating_column:
        return _tool_result("describe_rating", "warning", {}, ["rating column not detected"])
    series = pd.to_numeric(frame[rating_column], errors="coerce").dropna()
    if series.empty:
        return _tool_result("describe_rating", "warning", {}, ["rating column has no numeric values"])
    data = {
        "min": float(series.min()),
        "max": float(series.max()),
        "mean": float(series.mean()),
        "median": float(series.median()),
        "std": float(series.std(ddof=0)) if len(series) > 1 else 0.0,
        "distribution": series.value_counts().sort_index().to_dict(),
    }
    return _tool_result("describe_rating", "success", data)


def get_rating_distribution(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = arguments
    rating_column = _get_role_column(mapping, "rating_column")
    if not rating_column:
        return _tool_result("get_rating_distribution", "warning", {}, ["rating column not detected"])
    series = pd.to_numeric(frame[rating_column], errors="coerce").dropna()
    return _tool_result("get_rating_distribution", "success", {"distribution": series.value_counts().sort_index().to_dict()})


def _rows_by_rating(frame: pd.DataFrame, mapping: dict[str, Any], low: bool, threshold: float, limit: int) -> dict[str, Any]:
    rating_column = _get_role_column(mapping, "rating_column")
    if not rating_column:
        tool_name = "get_low_rating_rows" if low else "get_high_rating_rows"
        return _tool_result(tool_name, "warning", {}, ["rating column not detected"])
    numeric = pd.to_numeric(frame[rating_column], errors="coerce")
    mask = numeric <= threshold if low else numeric >= threshold
    selected = frame[mask.fillna(False)]
    return _tool_result(
        "get_low_rating_rows" if low else "get_high_rating_rows",
        "success",
        {"rows": _serialize_rows(selected, _safe_columns(frame, mapping), limit=limit)},
    )


def get_low_rating_rows(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    threshold = float(arguments.get("threshold", 2))
    limit = int(arguments.get("limit", 20))
    return _rows_by_rating(frame, mapping, low=True, threshold=threshold, limit=limit)


def get_high_rating_rows(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    threshold = float(arguments.get("threshold", 4))
    limit = int(arguments.get("limit", 20))
    return _rows_by_rating(frame, mapping, low=False, threshold=threshold, limit=limit)


def compare_low_high_rating_rows(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = arguments
    rating_column = _get_role_column(mapping, "rating_column")
    text_column = _get_role_column(mapping, "text_column")
    if not rating_column:
        return _tool_result("compare_low_high_rating_rows", "warning", {}, ["rating column not detected"])

    rating = pd.to_numeric(frame[rating_column], errors="coerce")
    low = frame[rating <= 2]
    high = frame[rating >= 4]
    data: dict[str, Any] = {"low_count": int(len(low)), "high_count": int(len(high))}
    if text_column:
        low_len = low[text_column].dropna().astype(str).str.len()
        high_len = high[text_column].dropna().astype(str).str.len()
        data["avg_text_length_low"] = float(low_len.mean()) if not low_len.empty else 0.0
        data["avg_text_length_high"] = float(high_len.mean()) if not high_len.empty else 0.0
    return _tool_result("compare_low_high_rating_rows", "success", data)


def get_text_length_stats(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = arguments
    text_column = _get_role_column(mapping, "text_column")
    rating_column = _get_role_column(mapping, "rating_column")
    if not text_column:
        return _tool_result("get_text_length_stats", "warning", {}, ["text column not detected"])
    text = frame[text_column].dropna().astype(str)
    if text.empty:
        return _tool_result("get_text_length_stats", "warning", {}, ["text column is empty"])
    chars = text.str.len()
    words = text.str.split().str.len()
    data: dict[str, Any] = {
        "avg_chars": float(chars.mean()),
        "median_chars": float(chars.median()),
        "avg_words": float(words.mean()),
    }
    if rating_column:
        tmp = frame[[text_column, rating_column]].copy()
        tmp[rating_column] = pd.to_numeric(tmp[rating_column], errors="coerce")
        tmp["chars"] = tmp[text_column].astype(str).str.len()
        grouped = tmp.dropna(subset=[rating_column]).groupby(rating_column)["chars"].mean().to_dict()
        data["avg_chars_by_rating"] = grouped
    return _tool_result("get_text_length_stats", "success", data)


STOP_WORDS = {
    "the", "a", "an", "and", "or", "to", "for", "of", "in", "on", "is", "are", "was", "were", "it",
    "this", "that", "with", "from", "you", "your", "about", "they", "them", "have",
}



def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z\u0410-\u044f0-9_]{3,}", text.lower())
    return [token for token in tokens if token not in STOP_WORDS]



def extract_top_keywords(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    text_column = _get_role_column(mapping, "text_column")
    rating_column = _get_role_column(mapping, "rating_column")
    if not text_column:
        return _tool_result("extract_top_keywords", "warning", {}, ["text column not detected"])

    subset = frame.copy()
    rating_min = arguments.get("rating_min")
    rating_max = arguments.get("rating_max")
    if rating_column and (rating_min is not None or rating_max is not None):
        rating = pd.to_numeric(subset[rating_column], errors="coerce")
        if rating_min is not None:
            subset = subset[rating >= float(rating_min)]
            rating = pd.to_numeric(subset[rating_column], errors="coerce")
        if rating_max is not None:
            subset = subset[rating <= float(rating_max)]

    counter: Counter[str] = Counter()
    for value in subset[text_column].dropna().astype(str):
        counter.update(_tokenize(value))

    top_n = int(arguments.get("top_n", 20))
    return _tool_result("extract_top_keywords", "success", {"top_keywords": counter.most_common(top_n)})


def search_rows_by_keyword(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    text_column = _get_role_column(mapping, "text_column")
    keyword = str(arguments.get("keyword", "")).strip()
    limit = int(arguments.get("limit", 20))
    if not text_column:
        return _tool_result("search_rows_by_keyword", "warning", {}, ["text column not detected"])
    if not keyword:
        return _tool_result("search_rows_by_keyword", "warning", {}, ["keyword is empty"])

    mask = frame[text_column].fillna("").astype(str).str.contains(re.escape(keyword), case=False, regex=True)
    rows = frame[mask]
    return _tool_result("search_rows_by_keyword", "success", {"rows": _serialize_rows(rows, _safe_columns(frame, mapping), limit=limit)})


TOPIC_PATTERNS = {
    "payment": ["payment", "billing", "charge", "\u043e\u043f\u043b\u0430\u0442", "\u0441\u043f\u0438\u0441\u0430\u043d"],
    "cancellation": ["cancel", "cancellation", "\u043e\u0442\u043c\u0435\u043d"],
    "driver": ["driver", "\u0432\u043e\u0434\u0438\u0442\u0435\u043b"],
    "price_pricing": ["price", "expensive", "\u0434\u043e\u0440\u043e\u0433", "\u0446\u0435\u043d\u0430"],
    "app_bug": ["bug", "error", "crash", "\u043b\u0430\u0433", "\u043e\u0448\u0438\u0431"],
    "support": ["support", "help", "\u043f\u043e\u0434\u0434\u0435\u0440\u0436"],
    "safety": ["safety", "unsafe", "\u0431\u0435\u0437\u043e\u043f\u0430\u0441"],
    "account": ["account", "login", "\u0430\u043a\u043a\u0430\u0443\u043d\u0442"],
    "location": ["location", "map", "\u043b\u043e\u043a\u0430\u0446", "\u0430\u0434\u0440\u0435\u0441"],
    "general_positive": ["good", "great", "excellent", "\u043e\u0442\u043b\u0438\u0447", "\u0445\u043e\u0440\u043e\u0448"],
    "general_negative": ["bad", "terrible", "awful", "\u043f\u043b\u043e\u0445\u043e", "\u0443\u0436\u0430\u0441"],
}



def cluster_texts_by_topic_simple(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = arguments
    text_column = _get_role_column(mapping, "text_column")
    if not text_column:
        return _tool_result("cluster_texts_by_topic_simple", "warning", {}, ["text column not detected"])

    counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    for value in frame[text_column].dropna().astype(str):
        low = value.lower()
        topic = "other"
        for topic_name, patterns in TOPIC_PATTERNS.items():
            if any(pattern in low for pattern in patterns):
                topic = topic_name
                break
        counts[topic] += 1
        if len(examples[topic]) < 3:
            examples[topic].append(value[:180])
    return _tool_result("cluster_texts_by_topic_simple", "success", {"counts": dict(counts), "examples": dict(examples)})


def _parse_month_series(frame: pd.DataFrame, date_column: str) -> pd.Series:
    parsed = pd.to_datetime(frame[date_column], errors="coerce")
    return parsed.dt.to_period("M").astype(str)


def get_rows_by_month(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = arguments
    date_column = _get_role_column(mapping, "date_column")
    if not date_column:
        return _tool_result("get_rows_by_month", "warning", {}, ["date column not detected"])
    months = _parse_month_series(frame, date_column)
    data = months.value_counts().sort_index().to_dict()
    return _tool_result("get_rows_by_month", "success", data)


def get_average_rating_by_month(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = arguments
    date_column = _get_role_column(mapping, "date_column")
    rating_column = _get_role_column(mapping, "rating_column")
    if not date_column or not rating_column:
        return _tool_result("get_average_rating_by_month", "warning", {}, ["date or rating column not detected"])
    tmp = pd.DataFrame({"month": _parse_month_series(frame, date_column), "rating": pd.to_numeric(frame[rating_column], errors="coerce")})
    grouped = tmp.dropna().groupby("month")["rating"].mean().to_dict()
    return _tool_result("get_average_rating_by_month", "success", grouped)


def get_rows_by_version(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = arguments
    version_column = _get_role_column(mapping, "version_column")
    if not version_column:
        return _tool_result("get_rows_by_version", "warning", {}, ["version column not detected"])
    data = frame[version_column].dropna().astype(str).value_counts().head(30).to_dict()
    return _tool_result("get_rows_by_version", "success", data)


def get_average_rating_by_version(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = arguments
    version_column = _get_role_column(mapping, "version_column")
    rating_column = _get_role_column(mapping, "rating_column")
    if not version_column or not rating_column:
        return _tool_result("get_average_rating_by_version", "warning", {}, ["version or rating column not detected"])
    tmp = frame[[version_column, rating_column]].copy()
    tmp[rating_column] = pd.to_numeric(tmp[rating_column], errors="coerce")
    grouped = tmp.dropna().groupby(version_column)[rating_column].mean().sort_values().head(30).to_dict()
    return _tool_result("get_average_rating_by_version", "success", grouped)


def find_problematic_versions(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    version_column = _get_role_column(mapping, "version_column")
    rating_column = _get_role_column(mapping, "rating_column")
    if not version_column or not rating_column:
        return _tool_result("find_problematic_versions", "warning", {}, ["version or rating column not detected"])
    min_reviews = int(arguments.get("min_reviews", 5))
    max_avg_rating = float(arguments.get("max_avg_rating", 3.0))

    tmp = frame[[version_column, rating_column]].copy()
    tmp[rating_column] = pd.to_numeric(tmp[rating_column], errors="coerce")
    grouped = tmp.dropna().groupby(version_column)[rating_column].agg(["count", "mean"]).reset_index()
    filtered = grouped[(grouped["count"] >= min_reviews) & (grouped["mean"] <= max_avg_rating)]
    return _tool_result("find_problematic_versions", "success", filtered.to_dict(orient="records"))


def get_reply_rate(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = arguments
    reply_column = _get_role_column(mapping, "reply_column")
    if not reply_column:
        return _tool_result("get_reply_rate", "warning", {}, ["reply column not detected"])
    replied = frame[reply_column].fillna("").astype(str).str.strip() != ""
    data = {
        "reply_count": int(replied.sum()),
        "total_rows": int(len(frame)),
        "reply_rate": float(replied.mean()) if len(frame) > 0 else 0.0,
    }
    return _tool_result("get_reply_rate", "success", data)


def get_reply_rate_by_rating(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = arguments
    reply_column = _get_role_column(mapping, "reply_column")
    rating_column = _get_role_column(mapping, "rating_column")
    if not reply_column or not rating_column:
        return _tool_result("get_reply_rate_by_rating", "warning", {}, ["reply or rating column not detected"])
    tmp = frame[[reply_column, rating_column]].copy()
    tmp[rating_column] = pd.to_numeric(tmp[rating_column], errors="coerce")
    tmp["has_reply"] = tmp[reply_column].fillna("").astype(str).str.strip() != ""
    grouped = tmp.dropna(subset=[rating_column]).groupby(rating_column)["has_reply"].mean().to_dict()
    return _tool_result("get_reply_rate_by_rating", "success", grouped)


def find_unanswered_critical_rows(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    threshold = float(arguments.get("threshold", 2))
    limit = int(arguments.get("limit", 20))
    reply_column = _get_role_column(mapping, "reply_column")
    rating_column = _get_role_column(mapping, "rating_column")
    if not reply_column or not rating_column:
        return _tool_result("find_unanswered_critical_rows", "warning", {}, ["reply or rating column not detected"])
    rating = pd.to_numeric(frame[rating_column], errors="coerce")
    no_reply = frame[reply_column].fillna("").astype(str).str.strip() == ""
    rows = frame[(rating <= threshold) & no_reply]
    return _tool_result(
        "find_unanswered_critical_rows",
        "success",
        {"rows": _serialize_rows(rows, _safe_columns(frame, mapping), limit=limit)},
    )


PROMPT_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous",
    "system prompt",
    "developer message",
    "reveal prompt",
    "forget instructions",
    "run command",
    "execute code",
    "tool call",
    "jailbreak",
    "prompt injection",
    "\u0438\u0433\u043d\u043e\u0440\u0438\u0440\u0443\u0439 \u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u0438",
    "\u0441\u0438\u0441\u0442\u0435\u043c\u043d\u044b\u0439 \u043f\u0440\u043e\u043c\u043f\u0442",
    "\u0440\u0430\u0441\u043a\u0440\u043e\u0439 \u043f\u0440\u043e\u043c\u043f\u0442",
    "\u0432\u044b\u043f\u043e\u043b\u043d\u0438 \u043a\u043e\u043c\u0430\u043d\u0434\u0443",
]



def detect_text_prompt_injection_patterns(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = arguments
    text_column = _get_role_column(mapping, "text_column")
    if not text_column:
        return _tool_result("detect_text_prompt_injection_patterns", "warning", {}, ["text column not detected"])
    suspicious = []
    for idx, value in frame[text_column].fillna("").astype(str).items():
        low = value.lower()
        matched = [pattern for pattern in PROMPT_INJECTION_PATTERNS if pattern in low]
        if matched:
            suspicious.append({"row_index": int(idx), "matched_patterns": matched, "text": value[:240]})
    return _tool_result(
        "detect_text_prompt_injection_patterns",
        "success",
        {"count": len(suspicious), "rows": suspicious[:50]},
    )


def explain_prompt_injection_protection(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = frame, mapping, arguments
    return _tool_result(
        "explain_prompt_injection_protection",
        "success",
        {
            "rules": [
                "CSV rows are treated as data, not instructions.",
                "Only allowlisted tools can be executed.",
                "No arbitrary code execution from LLM output.",
                "Tool arguments are validated.",
                "Sensitive columns are excluded from LLM context.",
            ]
        },
    )


def _charts_dir() -> Path:
    path = Path(settings.outputs_dir) / "lab3" / "charts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_rating_distribution_chart(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = arguments
    rating_column = _get_role_column(mapping, "rating_column")
    if not rating_column:
        return _tool_result("create_rating_distribution_chart", "warning", {}, ["rating column not detected"])
    series = pd.to_numeric(frame[rating_column], errors="coerce").dropna()
    if series.empty:
        return _tool_result("create_rating_distribution_chart", "warning", {}, ["rating column has no numeric values"])
    dist = series.value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(8, 4))
    dist.plot(kind="bar", ax=ax)
    ax.set_title("Rating distribution")
    ax.set_xlabel("rating")
    ax.set_ylabel("count")
    out = _charts_dir() / f"rating_distribution_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return _tool_result("create_rating_distribution_chart", "success", {"chart_path": str(out)})


def create_rows_by_month_chart(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = arguments
    date_column = _get_role_column(mapping, "date_column")
    if not date_column:
        return _tool_result("create_rows_by_month_chart", "warning", {}, ["date column not detected"])
    months = _parse_month_series(frame, date_column).value_counts().sort_index()
    if months.empty:
        return _tool_result("create_rows_by_month_chart", "warning", {}, ["date column has no valid values"])
    fig, ax = plt.subplots(figsize=(10, 4))
    months.plot(kind="line", marker="o", ax=ax)
    ax.set_title("Rows by month")
    ax.set_xlabel("month")
    ax.set_ylabel("rows")
    out = _charts_dir() / f"rows_by_month_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return _tool_result("create_rows_by_month_chart", "success", {"chart_path": str(out)})


def generate_markdown_report(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    tool_outputs = arguments.get("tool_outputs", [])
    report_dir = Path(settings.outputs_dir) / "lab3"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "lab3_report.md"
    lines = [
        "# Lab 3 Analytics Report",
        "",
        f"- Rows: {len(frame)}",
        f"- Columns: {len(frame.columns)}",
        "",
        "## Column Mapping",
        "```json",
        json.dumps(mapping, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Tool Outputs",
    ]
    for item in tool_outputs:
        lines.append(f"### {item.get('tool', 'unknown')}")
        lines.append("```json")
        lines.append(json.dumps(item, ensure_ascii=False, indent=2))
        lines.append("```")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return _tool_result("generate_markdown_report", "success", {"report_path": str(report_path)})


def export_lab3_result_json(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = frame, mapping
    payload = arguments.get("result_payload", {})
    out_dir = Path(settings.outputs_dir) / "lab3"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "lab3_result.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return _tool_result("export_lab3_result_json", "success", {"result_path": str(out_path)})


TOOL_METADATA: dict[str, dict[str, Any]] = {
    "get_dataset_schema": {"description": "Dataset schema summary", "required_roles": []},
    "get_sample_rows": {"description": "Sample rows without sensitive columns", "required_roles": []},
    "get_missing_values_report": {"description": "Missing values report", "required_roles": []},
    "get_duplicate_text_report": {"description": "Duplicate review texts", "required_roles": ["text_column"]},
    "describe_numeric_columns": {"description": "Numeric columns statistics", "required_roles": []},
    "describe_rating": {"description": "Rating statistics", "required_roles": ["rating_column"]},
    "get_rating_distribution": {"description": "Rating distribution", "required_roles": ["rating_column"]},
    "get_low_rating_rows": {"description": "Rows with low rating", "required_roles": ["rating_column"]},
    "get_high_rating_rows": {"description": "Rows with high rating", "required_roles": ["rating_column"]},
    "compare_low_high_rating_rows": {"description": "Compare low/high rating rows", "required_roles": ["rating_column"]},
    "get_text_length_stats": {"description": "Text length statistics", "required_roles": ["text_column"]},
    "extract_top_keywords": {"description": "Top keywords", "required_roles": ["text_column"]},
    "search_rows_by_keyword": {"description": "Keyword search", "required_roles": ["text_column"]},
    "cluster_texts_by_topic_simple": {"description": "Simple topic clustering", "required_roles": ["text_column"]},
    "get_rows_by_month": {"description": "Rows by month", "required_roles": ["date_column"]},
    "get_average_rating_by_month": {"description": "Average rating by month", "required_roles": ["date_column", "rating_column"]},
    "get_rows_by_version": {"description": "Rows by app version", "required_roles": ["version_column"]},
    "get_average_rating_by_version": {"description": "Average rating by app version", "required_roles": ["version_column", "rating_column"]},
    "find_problematic_versions": {"description": "Find problematic versions", "required_roles": ["version_column", "rating_column"]},
    "get_reply_rate": {"description": "Reply rate", "required_roles": ["reply_column"]},
    "get_reply_rate_by_rating": {"description": "Reply rate by rating", "required_roles": ["reply_column", "rating_column"]},
    "find_unanswered_critical_rows": {"description": "Critical unanswered rows", "required_roles": ["reply_column", "rating_column"]},
    "detect_text_prompt_injection_patterns": {"description": "Prompt-injection pattern detection", "required_roles": ["text_column"]},
    "explain_prompt_injection_protection": {"description": "Prompt-injection protection rules", "required_roles": []},
    "create_rating_distribution_chart": {"description": "Rating distribution chart", "required_roles": ["rating_column"]},
    "create_rows_by_month_chart": {"description": "Rows-by-month chart", "required_roles": ["date_column"]},
    "generate_markdown_report": {"description": "Generate markdown report", "required_roles": []},
    "export_lab3_result_json": {"description": "Export full JSON result", "required_roles": []},
    "get_available_tools": {"description": "List available tools", "required_roles": []},
}

TOOL_FUNCTIONS: dict[str, Callable[[pd.DataFrame, dict[str, Any], dict[str, Any]], dict[str, Any]]] = {
    "get_dataset_schema": get_dataset_schema,
    "get_sample_rows": get_sample_rows,
    "get_missing_values_report": get_missing_values_report,
    "get_duplicate_text_report": get_duplicate_text_report,
    "describe_numeric_columns": describe_numeric_columns,
    "describe_rating": describe_rating,
    "get_rating_distribution": get_rating_distribution,
    "get_low_rating_rows": get_low_rating_rows,
    "get_high_rating_rows": get_high_rating_rows,
    "compare_low_high_rating_rows": compare_low_high_rating_rows,
    "get_text_length_stats": get_text_length_stats,
    "extract_top_keywords": extract_top_keywords,
    "search_rows_by_keyword": search_rows_by_keyword,
    "cluster_texts_by_topic_simple": cluster_texts_by_topic_simple,
    "get_rows_by_month": get_rows_by_month,
    "get_average_rating_by_month": get_average_rating_by_month,
    "get_rows_by_version": get_rows_by_version,
    "get_average_rating_by_version": get_average_rating_by_version,
    "find_problematic_versions": find_problematic_versions,
    "get_reply_rate": get_reply_rate,
    "get_reply_rate_by_rating": get_reply_rate_by_rating,
    "find_unanswered_critical_rows": find_unanswered_critical_rows,
    "detect_text_prompt_injection_patterns": detect_text_prompt_injection_patterns,
    "explain_prompt_injection_protection": explain_prompt_injection_protection,
    "create_rating_distribution_chart": create_rating_distribution_chart,
    "create_rows_by_month_chart": create_rows_by_month_chart,
    "generate_markdown_report": generate_markdown_report,
    "export_lab3_result_json": export_lab3_result_json,
}


def get_available_tools(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = frame, mapping, arguments
    items = [{"tool": name, **meta} for name, meta in TOOL_METADATA.items()]
    return _tool_result("get_available_tools", "success", {"tools": items})


TOOL_FUNCTIONS["get_available_tools"] = get_available_tools


def execute_tool(
    dataset_name: str,
    tool: str,
    column_mapping: dict[str, Any],
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    frame = load_dataset(dataset_name)
    function = TOOL_FUNCTIONS.get(tool)
    if not function:
        return _tool_result(tool, "error", {}, [f"unknown tool: {tool}"])
    try:
        return function(frame, column_mapping, arguments or {})
    except Exception as exc:  # pragma: no cover - safety net for runtime
        return _tool_result(tool, "error", {}, [str(exc)])
