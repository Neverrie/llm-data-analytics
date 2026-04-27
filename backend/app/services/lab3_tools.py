from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import matplotlib
import pandas as pd

from app.config import settings
from app.services.lab3_column_mapper import load_dataset
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
    sample = frame[columns].head(limit)
    return sample.where(pd.notna(sample), None).to_dict(orient="records")


def _numeric_columns(frame: pd.DataFrame, mapping: dict[str, Any]) -> list[str]:
    mapped = [c for c in mapping.get("numeric_columns", []) if c in frame.columns]
    if mapped:
        return mapped
    return frame.select_dtypes(include=["number"]).columns.tolist()


def _categorical_columns(frame: pd.DataFrame, mapping: dict[str, Any]) -> list[str]:
    mapped = [c for c in mapping.get("categorical_columns", []) if c in frame.columns]
    if mapped:
        return mapped
    fallback: list[str] = []
    for column in frame.columns:
        non_null = frame[column].dropna()
        if non_null.empty:
            continue
        if non_null.nunique(dropna=True) / max(len(non_null), 1) <= 0.2:
            fallback.append(column)
    return fallback


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
    return _tool_result("get_missing_values_report", "success", {column: int(frame[column].isna().sum()) for column in frame.columns})


def get_duplicate_text_report(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = arguments
    text_column = _get_role_column(mapping, "text_column")
    if not text_column:
        return _tool_result("get_duplicate_text_report", "warning", {}, ["text column not detected"])
    duplicates = frame[frame[text_column].duplicated(keep=False) & frame[text_column].notna()]
    sample = duplicates[[text_column]].head(10).astype(str).to_dict(orient="records")
    return _tool_result("get_duplicate_text_report", "success", {"duplicates_count": int(len(duplicates)), "sample_duplicates": sample})


def describe_numeric_columns(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = arguments
    numeric = frame[_numeric_columns(frame, mapping)]
    if numeric.empty:
        return _tool_result("describe_numeric_columns", "warning", {}, ["no numeric columns detected"])
    return _tool_result("describe_numeric_columns", "success", numeric.describe().to_dict())


def describe_categorical_columns(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    max_columns = int(arguments.get("max_columns", 10))
    top_n = int(arguments.get("top_n", 10))
    columns = _categorical_columns(frame, mapping)[:max_columns]
    if not columns:
        return _tool_result("describe_categorical_columns", "warning", {}, ["no categorical columns detected"])
    data: dict[str, Any] = {}
    for column in columns:
        counts = frame[column].fillna("<NA>").astype(str).value_counts().head(top_n)
        data[column] = {"unique_count": int(frame[column].nunique(dropna=True)), "top_values": counts.to_dict()}
    return _tool_result("describe_categorical_columns", "success", data)


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
    tool_name = "get_low_rating_rows" if low else "get_high_rating_rows"
    return _tool_result(tool_name, "success", {"rows": _serialize_rows(selected, _safe_columns(frame, mapping), limit=limit)})


def get_low_rating_rows(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    return _rows_by_rating(frame, mapping, low=True, threshold=float(arguments.get("threshold", 2)), limit=int(arguments.get("limit", 20)))


def get_high_rating_rows(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    return _rows_by_rating(frame, mapping, low=False, threshold=float(arguments.get("threshold", 4)), limit=int(arguments.get("limit", 20)))


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
    data: dict[str, Any] = {"avg_chars": float(chars.mean()), "median_chars": float(chars.median()), "avg_words": float(words.mean())}
    if rating_column:
        tmp = frame[[text_column, rating_column]].copy()
        tmp[rating_column] = pd.to_numeric(tmp[rating_column], errors="coerce")
        tmp["chars"] = tmp[text_column].astype(str).str.len()
        data["avg_chars_by_rating"] = tmp.dropna(subset=[rating_column]).groupby(rating_column)["chars"].mean().to_dict()
    return _tool_result("get_text_length_stats", "success", data)


STOP_WORDS = {
    "the", "a", "an", "and", "or", "to", "for", "of", "in", "on", "is", "are", "was", "were", "it",
    "this", "that", "with", "from", "you", "your", "about", "they", "them", "have",
    "это", "как", "что", "для", "или", "когда", "где", "кто", "при", "под", "без", "если",
}


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-zА-Яа-я0-9_]{3,}", text.lower())
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
    return _tool_result("search_rows_by_keyword", "success", {"rows": _serialize_rows(frame[mask], _safe_columns(frame, mapping), limit=limit)})


TOPIC_PATTERNS = {
    "payment": ["payment", "billing", "charge", "оплат", "списан"],
    "cancellation": ["cancel", "cancellation", "отмен"],
    "driver": ["driver", "водител"],
    "price_pricing": ["price", "expensive", "дорог", "цена"],
    "app_bug": ["bug", "error", "crash", "лаг", "ошиб"],
    "support": ["support", "help", "поддерж"],
    "safety": ["safety", "unsafe", "безопас"],
    "account": ["account", "login", "аккаунт"],
    "location": ["location", "map", "локац", "адрес"],
    "general_positive": ["good", "great", "excellent", "отлич", "хорош"],
    "general_negative": ["bad", "terrible", "awful", "плохо", "ужас"],
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
    return _tool_result("get_rows_by_month", "success", months.value_counts().sort_index().to_dict())


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
    return _tool_result("get_rows_by_version", "success", frame[version_column].dropna().astype(str).value_counts().head(30).to_dict())


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
    data = {"reply_count": int(replied.sum()), "total_rows": int(len(frame)), "reply_rate": float(replied.mean()) if len(frame) > 0 else 0.0}
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
    return _tool_result("find_unanswered_critical_rows", "success", {"rows": _serialize_rows(rows, _safe_columns(frame, mapping), limit=limit)})


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
    "игнорируй инструкции",
    "системный промпт",
    "раскрой промпт",
    "выполни команду",
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
    return _tool_result("detect_text_prompt_injection_patterns", "success", {"count": len(suspicious), "rows": suspicious[:50]})


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


def get_correlation_matrix(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    limit = int(arguments.get("limit", 20))
    numeric_cols = _numeric_columns(frame, mapping)
    if len(numeric_cols) < 2:
        return _tool_result("get_correlation_matrix", "warning", {}, ["at least two numeric columns are required"])
    corr = frame[numeric_cols].corr(numeric_only=True)
    pairs: list[dict[str, Any]] = []
    columns = corr.columns.tolist()
    for i, col_a in enumerate(columns):
        for j in range(i + 1, len(columns)):
            col_b = columns[j]
            value = corr.loc[col_a, col_b]
            if pd.isna(value):
                continue
            pairs.append({"column_a": col_a, "column_b": col_b, "correlation": float(value), "abs_correlation": float(abs(value))})
    pairs.sort(key=lambda item: item["abs_correlation"], reverse=True)
    return _tool_result("get_correlation_matrix", "success", {"top_correlations": pairs[:limit], "numeric_columns": numeric_cols})


def detect_numeric_outliers(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    limit_examples = int(arguments.get("limit_examples", 5))
    numeric_cols = _numeric_columns(frame, mapping)
    if not numeric_cols:
        return _tool_result("detect_numeric_outliers", "warning", {}, ["no numeric columns detected"])
    result: dict[str, Any] = {}
    for column in numeric_cols:
        series = pd.to_numeric(frame[column], errors="coerce").dropna()
        if series.empty:
            result[column] = {"q1": None, "q3": None, "iqr": None, "lower_bound": None, "upper_bound": None, "outlier_count": 0, "examples": []}
            continue
        q1 = float(series.quantile(0.25))
        q3 = float(series.quantile(0.75))
        iqr = float(q3 - q1)
        lower = float(q1 - 1.5 * iqr)
        upper = float(q3 + 1.5 * iqr)
        outliers = series[(series < lower) | (series > upper)]
        result[column] = {
            "q1": q1,
            "q3": q3,
            "iqr": iqr,
            "lower_bound": lower,
            "upper_bound": upper,
            "outlier_count": int(outliers.shape[0]),
            "examples": [float(v) for v in outliers.head(limit_examples).tolist()],
        }
    return _tool_result("detect_numeric_outliers", "success", result)


def infer_potential_target_columns(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = mapping, arguments
    candidates: list[dict[str, Any]] = []
    for column in frame.columns:
        low = column.lower()
        non_null = frame[column].dropna()
        unique_count = int(non_null.nunique(dropna=True)) if not non_null.empty else 0
        ratio = unique_count / max(len(non_null), 1) if not non_null.empty else 0.0
        if any(token in low for token in ["target", "label", "class", "outcome", "result", "passed", "final_score", "grade", "статус", "результат", "оцен"]):
            candidates.append({"column": column, "confidence": 0.9, "reason": "name indicates target semantics"})
            continue
        if unique_count in {2, 3, 4, 5, 6, 7, 8} and ratio <= 0.2:
            candidates.append({"column": column, "confidence": 0.7, "reason": "low-cardinality candidate"})
            continue
        if pd.api.types.is_numeric_dtype(frame[column]) and any(token in low for token in ["score", "grade", "result"]):
            candidates.append({"column": column, "confidence": 0.65, "reason": "numeric score-like candidate"})
    best: dict[str, dict[str, Any]] = {}
    for item in candidates:
        prev = best.get(item["column"])
        if prev is None or item["confidence"] > prev["confidence"]:
            best[item["column"]] = item
    ordered = sorted(best.values(), key=lambda x: x["confidence"], reverse=True)
    return _tool_result("infer_potential_target_columns", "success", {"candidates": ordered})


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
    "describe_categorical_columns": {"description": "Categorical columns analysis", "required_roles": []},
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
    "get_correlation_matrix": {"description": "Top numeric correlations", "required_roles": []},
    "detect_numeric_outliers": {"description": "Numeric outlier detection with IQR", "required_roles": []},
    "infer_potential_target_columns": {"description": "Potential target column candidates", "required_roles": []},
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
    "describe_categorical_columns": describe_categorical_columns,
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
    "get_correlation_matrix": get_correlation_matrix,
    "detect_numeric_outliers": detect_numeric_outliers,
    "infer_potential_target_columns": infer_potential_target_columns,
    "create_rating_distribution_chart": create_rating_distribution_chart,
    "create_rows_by_month_chart": create_rows_by_month_chart,
    "generate_markdown_report": generate_markdown_report,
    "export_lab3_result_json": export_lab3_result_json,
}


def get_available_tools(frame: pd.DataFrame, mapping: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _ = frame, mapping, arguments
    return _tool_result("get_available_tools", "success", {"tools": [{"tool": name, **meta} for name, meta in TOOL_METADATA.items()]})


TOOL_FUNCTIONS["get_available_tools"] = get_available_tools


def execute_tool(dataset_name: str, tool: str, column_mapping: dict[str, Any], arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    frame = load_dataset(dataset_name)
    function = TOOL_FUNCTIONS.get(tool)
    if not function:
        return _tool_result(tool, "error", {}, [f"unknown tool: {tool}"])
    try:
        return function(frame, column_mapping, arguments or {})
    except Exception as exc:  # pragma: no cover
        return _tool_result(tool, "error", {}, [str(exc)])
