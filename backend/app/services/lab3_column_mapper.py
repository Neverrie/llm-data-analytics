from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import settings
from app.ollama_client import OllamaClient, OllamaClientError
from app.schemas import Lab3ColumnMapping, RoleMatch
from app.services.lab2_service import Lab2PipelineError

ROLE_NAMES = [
    "id_column",
    "text_column",
    "rating_column",
    "date_column",
    "version_column",
    "reply_column",
    "reply_date_column",
    "username_column",
    "image_column",
]


def list_datasets() -> list[dict[str, str]]:
    datasets_dir = Path(settings.datasets_dir)
    allowed = {".csv": "csv", ".xlsx": "xlsx", ".xls": "xls"}
    items: list[dict[str, str]] = []
    for path in sorted(datasets_dir.glob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in allowed:
            items.append(
                {
                    "name": path.name,
                    "path": f"datasets/{path.name}",
                    "type": allowed[suffix],
                }
            )
    return items


def load_dataset(dataset_name: str) -> pd.DataFrame:
    dataset_path = Path(settings.datasets_dir) / dataset_name
    if not dataset_path.exists():
        raise Lab2PipelineError(f"Dataset '{dataset_name}' was not found in {settings.datasets_dir}.", status_code=404)

    suffix = dataset_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(dataset_path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(dataset_path)
    raise Lab2PipelineError(f"Unsupported dataset type for '{dataset_name}'.", status_code=400)


def _sample_values(series: pd.Series, max_items: int = 3) -> list[str]:
    return [str(item) for item in series.dropna().astype(str).head(max_items).tolist()]


def _is_date_like(series: pd.Series) -> bool:
    sample = series.dropna().astype(str).head(200)
    if sample.empty:
        return False
    parsed = pd.to_datetime(sample, errors="coerce")
    return parsed.notna().mean() >= 0.7


def profile_dataset(dataset_name: str) -> dict[str, Any]:
    frame = load_dataset(dataset_name)
    dtypes = {column: str(dtype) for column, dtype in frame.dtypes.items()}
    missing_values = {column: int(frame[column].isna().sum()) for column in frame.columns}
    sample_values = {column: _sample_values(frame[column]) for column in frame.columns}

    numeric_columns = [column for column in frame.columns if pd.api.types.is_numeric_dtype(frame[column])]
    text_like_columns = [column for column in frame.columns if frame[column].dtype == "object"]
    date_like_columns = [column for column in frame.columns if _is_date_like(frame[column])]

    categorical_columns: list[str] = []
    for column in frame.columns:
        unique_non_null = frame[column].nunique(dropna=True)
        if unique_non_null == 0:
            continue
        ratio = unique_non_null / max(len(frame), 1)
        if ratio <= 0.2 and column not in numeric_columns:
            categorical_columns.append(column)

    return {
        "dataset_name": dataset_name,
        "total_rows": int(len(frame)),
        "total_columns": int(len(frame.columns)),
        "columns": [str(column) for column in frame.columns.tolist()],
        "dtypes": dtypes,
        "missing_values": missing_values,
        "sample_values": sample_values,
        "numeric_columns": numeric_columns,
        "text_like_columns": text_like_columns,
        "date_like_columns": date_like_columns,
        "categorical_columns": categorical_columns,
    }


def _match_by_name(columns: list[str], patterns: list[str]) -> str | None:
    lowered = {column: column.lower() for column in columns}
    for pattern in patterns:
        for original, low in lowered.items():
            if pattern in low:
                return original
    return None


def _role(column: str | None, confidence: float, reason: str) -> RoleMatch:
    return RoleMatch(column=column, confidence=confidence, reason=reason)


def infer_column_roles_heuristic(profile: dict[str, Any]) -> Lab3ColumnMapping:
    columns: list[str] = profile["columns"]
    numeric_columns: list[str] = profile["numeric_columns"]
    date_like_columns: list[str] = profile["date_like_columns"]
    text_like_columns: list[str] = profile["text_like_columns"]
    frame = load_dataset(profile["dataset_name"])

    roles: dict[str, RoleMatch] = {}

    id_column = _match_by_name(columns, ["id", "uuid"])
    if id_column and frame[id_column].nunique(dropna=True) / max(len(frame), 1) > 0.8:
        roles["id_column"] = _role(id_column, 0.85, "column name indicates id and values are mostly unique")
    else:
        roles["id_column"] = _role(None, 0.0, "no suitable column found")

    text_by_name = _match_by_name(
        columns,
        [
            "content",
            "review",
            "comment",
            "text",
            "message",
            "body",
            "отзыв",
            "коммент",
            "текст",
        ],
    )
    text_column = text_by_name
    if not text_column:
        best = None
        best_score = -1.0
        for column in text_like_columns:
            values = frame[column].dropna().astype(str)
            if values.empty:
                continue
            avg_len = values.str.len().mean()
            unique_ratio = values.nunique() / max(len(values), 1)
            score = (avg_len / 200.0) + unique_ratio
            if score > best_score:
                best_score = score
                best = column
        text_column = best
    roles["text_column"] = (
        _role(text_column, 0.9, "column name/text statistics suggest review text")
        if text_column
        else _role(None, 0.0, "no suitable column found")
    )

    rating_candidate = _match_by_name(columns, ["score", "rating", "stars", "star", "оцен", "рейтинг", "балл"])
    if rating_candidate and rating_candidate in numeric_columns:
        roles["rating_column"] = _role(rating_candidate, 0.95, "column name contains score/rating and values are numeric")
    else:
        selected = None
        for column in numeric_columns:
            series = pd.to_numeric(frame[column], errors="coerce").dropna()
            if series.empty:
                continue
            min_value = float(series.min())
            max_value = float(series.max())
            cardinality = series.nunique()
            if ((1 <= min_value <= 5 and 1 <= max_value <= 5) or (0 <= min_value <= 10 and 0 <= max_value <= 10)) and cardinality <= 15:
                selected = column
                break
        roles["rating_column"] = (
            _role(selected, 0.8, "numeric values look like rating scale")
            if selected
            else _role(None, 0.0, "no suitable column found")
        )

    date_column = None
    date_priority = ["at", "created_at", "date", "time", "timestamp", "дата", "время"]
    lowered = {column: column.lower() for column in columns}
    for key in date_priority:
        for original, low in lowered.items():
            if key in low and "version" not in low:
                date_column = original
                break
        if date_column:
            break
    if not date_column and date_like_columns:
        date_column = date_like_columns[0]
    roles["date_column"] = (
        _role(date_column, 0.85, "column name/date parsing indicates date field")
        if date_column
        else _role(None, 0.0, "no suitable column found")
    )

    version_column = None
    for preferred in ("appversion", "app_version", "version", "build"):
        for column in columns:
            if preferred in column.lower():
                version_column = column
                break
        if version_column:
            break
    roles["version_column"] = (
        _role(version_column, 0.9, "column name indicates software version")
        if version_column
        else _role(None, 0.0, "no suitable column found")
    )

    reply_column = _match_by_name(columns, ["reply", "response", "answer", "ответ"])
    roles["reply_column"] = (
        _role(reply_column, 0.88, "column name indicates reply text")
        if reply_column
        else _role(None, 0.0, "no suitable column found")
    )

    reply_date_column = _match_by_name(columns, ["replied", "reply_date", "response_date", "repliedat"])
    roles["reply_date_column"] = (
        _role(reply_date_column, 0.88, "column name indicates reply date")
        if reply_date_column
        else _role(None, 0.0, "no suitable column found")
    )

    username_column = _match_by_name(columns, ["username", "user_name", "author", "пользователь", "name"])
    roles["username_column"] = (
        _role(username_column, 0.7, "column name indicates username")
        if username_column
        else _role(None, 0.0, "no suitable column found")
    )

    image_column = _match_by_name(columns, ["image", "avatar", "photo", "picture"])
    roles["image_column"] = (
        _role(image_column, 0.8, "column name indicates image/avatar")
        if image_column
        else _role(None, 0.0, "no suitable column found")
    )

    return Lab3ColumnMapping(
        roles=roles,
        numeric_columns=profile["numeric_columns"],
        categorical_columns=profile["categorical_columns"],
    )


def _validate_llm_roles(raw: dict[str, Any], columns: list[str], fallback: Lab3ColumnMapping) -> Lab3ColumnMapping:
    roles = dict(fallback.roles)
    raw_roles = raw.get("roles")
    if not isinstance(raw_roles, dict):
        return fallback

    for role_name in ROLE_NAMES:
        value = raw_roles.get(role_name)
        if not isinstance(value, dict):
            continue
        column = value.get("column")
        confidence = value.get("confidence")
        reason = value.get("reason")
        if column is not None and column not in columns:
            continue
        try:
            confidence_float = float(confidence)
        except (TypeError, ValueError):
            continue
        confidence_float = min(max(confidence_float, 0.0), 1.0)
        reason_text = str(reason or "llm mapping")
        roles[role_name] = RoleMatch(column=column, confidence=confidence_float, reason=reason_text)

    return Lab3ColumnMapping(roles=roles, numeric_columns=fallback.numeric_columns, categorical_columns=fallback.categorical_columns)


async def infer_column_roles_llm(profile: dict[str, Any], heuristic_mapping: Lab3ColumnMapping) -> Lab3ColumnMapping:
    client = OllamaClient(settings.ollama_base_url)
    prompt = (
        "You are a data schema mapper. Return strict JSON only.\n"
        "Map semantic roles to existing columns.\n"
        "Allowed role names: id_column,text_column,rating_column,date_column,version_column,reply_column,reply_date_column,username_column,image_column.\n"
        "If unknown set column null and confidence 0.\n"
        f"Profile: {json.dumps(profile, ensure_ascii=False)}\n"
        f"Heuristic mapping: {heuristic_mapping.model_dump_json()}\n"
        "Output JSON format: {\"roles\": {\"text_column\": {\"column\": \"...\", \"confidence\": 0.0, \"reason\": \"...\"}}}\n"
    )
    try:
        response = await client.generate_json(settings.lab3_planner_model, prompt)
        parsed = json.loads(response.response)
    except (OllamaClientError, json.JSONDecodeError):
        return heuristic_mapping

    return _validate_llm_roles(parsed, columns=profile["columns"], fallback=heuristic_mapping)


async def get_effective_column_mapping(dataset_name: str, user_overrides: dict[str, str | None]) -> tuple[dict[str, Any], Lab3ColumnMapping]:
    profile = profile_dataset(dataset_name)
    heuristic = infer_column_roles_heuristic(profile)
    llm_mapping = await infer_column_roles_llm(profile, heuristic)

    merged_roles = dict(llm_mapping.roles)
    for role_name, column_name in user_overrides.items():
        if role_name not in ROLE_NAMES:
            raise Lab2PipelineError(f"Unknown override role '{role_name}'.")
        if column_name is not None and column_name not in profile["columns"]:
            raise Lab2PipelineError(
                f"Invalid column override for role '{role_name}'. Column '{column_name}' does not exist.",
                status_code=400,
            )
        merged_roles[role_name] = RoleMatch(
            column=column_name,
            confidence=1.0 if column_name else 0.0,
            reason="user override",
        )

    final_mapping = Lab3ColumnMapping(
        roles=merged_roles,
        numeric_columns=llm_mapping.numeric_columns,
        categorical_columns=llm_mapping.categorical_columns,
    )
    return profile, final_mapping
