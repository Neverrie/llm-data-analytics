from __future__ import annotations

import json
import re
import warnings
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
    "target_column",
    "date_column",
    "version_column",
    "reply_column",
    "reply_date_column",
    "username_column",
    "image_column",
]

ALLOWED_DATASET_SUFFIXES = {".csv": "csv", ".xlsx": "xlsx", ".xls": "xls"}
ID_NAME_PATTERNS = ["id", "student_id", "user_id", "uuid", "guid", "key", "code", "номер", "идентификатор"]
TEXT_NAME_PATTERNS = [
    "content",
    "text",
    "review",
    "comment",
    "message",
    "body",
    "description",
    "feedback",
    "отзыв",
    "комментар",
    "текст",
    "описан",
]
DATE_NAME_PATTERNS = [
    "date",
    "time",
    "created",
    "created_at",
    "updated",
    "timestamp",
    "at",
    "repliedat",
    "replied_at",
    "дата",
    "время",
]
DATE_EXCLUDE_PATTERNS = [
    "rate",
    "ratio",
    "percent",
    "percentage",
    "score",
    "grade",
    "amount",
    "price",
    "count",
    "total",
    "age",
    "id",
    "code",
    "key",
]
RATING_NAME_PATTERNS = ["final_score", "score", "rating", "stars", "star", "grade", "previous_score", "балл", "оцен"]
TARGET_NAME_PATTERNS = [
    "target",
    "label",
    "class",
    "outcome",
    "result",
    "passed",
    "final_score",
    "final_grade",
    "final_result",
    "статус",
    "результат",
    "оценка",
]


def _datasets_root() -> Path:
    return Path(settings.datasets_dir).resolve()


def resolve_dataset_path(dataset_name: str) -> Path:
    root = _datasets_root()
    normalized = dataset_name.replace("\\", "/").strip().lstrip("/")
    if not normalized:
        raise Lab2PipelineError("Dataset name is required.", status_code=400)

    candidate = (root / normalized).resolve()
    if root not in candidate.parents and candidate != root:
        raise Lab2PipelineError("Dataset path traversal is not allowed.", status_code=400)
    if not candidate.exists() or not candidate.is_file():
        raise Lab2PipelineError(f"Dataset '{dataset_name}' was not found in {settings.datasets_dir}.", status_code=404)
    if candidate.suffix.lower() not in ALLOWED_DATASET_SUFFIXES:
        raise Lab2PipelineError(f"Unsupported dataset type for '{dataset_name}'.", status_code=400)
    return candidate


def list_datasets() -> list[dict[str, str]]:
    datasets_dir = _datasets_root()
    items: list[dict[str, str]] = []
    for path in sorted(datasets_dir.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in ALLOWED_DATASET_SUFFIXES:
            continue
        relative = path.relative_to(datasets_dir).as_posix()
        items.append(
            {
                "name": relative,
                "path": f"datasets/{relative}",
                "type": ALLOWED_DATASET_SUFFIXES[suffix],
            }
        )
    return items


def load_dataset(dataset_name: str) -> pd.DataFrame:
    dataset_path = resolve_dataset_path(dataset_name)
    suffix = dataset_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(dataset_path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(dataset_path)
    raise Lab2PipelineError(f"Unsupported dataset type for '{dataset_name}'.", status_code=400)


def _sample_values(series: pd.Series, max_items: int = 3) -> list[str]:
    return [str(item) for item in series.dropna().astype(str).head(max_items).tolist()]


def looks_like_date_string(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    patterns = [
        r"^\d{4}-\d{2}-\d{2}$",
        r"^\d{4}/\d{2}/\d{2}$",
        r"^\d{2}\.\d{2}\.\d{4}$",
        r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?$",
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(?:\.\d+)?(?:Z|[+\-]\d{2}:\d{2})?$",
    ]
    return any(re.match(pattern, text) for pattern in patterns)


def _parse_datetimes_safely(sample: pd.Series) -> pd.Series:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        try:
            return pd.to_datetime(sample, errors="coerce", utc=False, format="mixed")
        except TypeError:
            return pd.to_datetime(sample, errors="coerce", utc=False)


def _is_date_like_series(column_name: str, series: pd.Series) -> bool:
    if pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series):
        return False
    low_name = column_name.lower()
    if any(part in low_name for part in DATE_EXCLUDE_PATTERNS):
        return False

    sample = series.dropna().astype(str).str.strip().head(200)
    if sample.empty:
        return False

    looks_like_ratio = sample.apply(looks_like_date_string).mean()
    name_is_date_like = _column_name_has(column_name, DATE_NAME_PATTERNS)
    if not name_is_date_like and looks_like_ratio < 0.5:
        return False
    if name_is_date_like and looks_like_ratio < 0.15:
        return False

    parsed = _parse_datetimes_safely(sample)
    return parsed.notna().mean() >= 0.7


def profile_dataset(dataset_name: str) -> dict[str, Any]:
    frame = load_dataset(dataset_name)
    dtypes = {column: str(dtype) for column, dtype in frame.dtypes.items()}
    missing_values = {column: int(frame[column].isna().sum()) for column in frame.columns}
    sample_values = {column: _sample_values(frame[column]) for column in frame.columns}

    numeric_columns = [column for column in frame.columns if pd.api.types.is_numeric_dtype(frame[column])]
    text_like_columns = [column for column in frame.columns if pd.api.types.is_object_dtype(frame[column]) or pd.api.types.is_string_dtype(frame[column])]
    date_like_columns = [column for column in frame.columns if _is_date_like_series(column, frame[column])]

    categorical_columns: list[str] = []
    for column in frame.columns:
        non_null = frame[column].dropna()
        if non_null.empty:
            continue
        unique_non_null = non_null.nunique(dropna=True)
        ratio = unique_non_null / max(len(non_null), 1)
        if ratio <= 0.2:
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


def _role(column: str | None, confidence: float, reason: str) -> RoleMatch:
    return RoleMatch(column=column, confidence=confidence, reason=reason)


def _column_name_has(column: str, patterns: list[str]) -> bool:
    low = column.lower()
    return any(pattern in low for pattern in patterns)


def _is_id_like_column(column: str, frame: pd.DataFrame) -> bool:
    low = column.lower()
    if any(pattern in low for pattern in ID_NAME_PATTERNS):
        values = frame[column].dropna().astype(str)
        if values.empty:
            return True
        avg_len = values.str.len().mean()
        return avg_len < 30
    return False


def _best_numeric_rating_candidate(frame: pd.DataFrame, numeric_columns: list[str]) -> str | None:
    preferred = ["final_score", "score", "rating", "stars", "star", "grade", "previous_score"]
    lowered = {c: c.lower() for c in numeric_columns}
    for name in preferred:
        for original, low in lowered.items():
            if name == low or low.endswith(name) or name in low:
                return original

    for column in numeric_columns:
        series = pd.to_numeric(frame[column], errors="coerce").dropna()
        if series.empty:
            continue
        min_value = float(series.min())
        max_value = float(series.max())
        cardinality = series.nunique()
        if ((0 <= min_value <= 10 and 0 <= max_value <= 10) or (1 <= min_value <= 5 and 1 <= max_value <= 5)) and cardinality <= 30:
            return column
    return None


def _infer_target_column(frame: pd.DataFrame, columns: list[str], categorical_columns: list[str], numeric_columns: list[str]) -> RoleMatch:
    for column in columns:
        if _column_name_has(column, TARGET_NAME_PATTERNS):
            return _role(column, 0.9, "column name strongly matches target/label semantics")

    for column in categorical_columns:
        non_null = frame[column].dropna()
        if non_null.empty:
            continue
        unique_count = non_null.nunique(dropna=True)
        if 2 <= unique_count <= 8:
            return _role(column, 0.7, "low-cardinality categorical column may be a target")

    for column in numeric_columns:
        low = column.lower()
        if any(token in low for token in ["final_score", "grade", "result"]):
            return _role(column, 0.7, "score-like numeric column may be a target")

    return _role(None, 0.0, "no suitable target column found")


def infer_column_roles_heuristic(profile: dict[str, Any]) -> Lab3ColumnMapping:
    columns: list[str] = profile["columns"]
    numeric_columns: list[str] = profile["numeric_columns"]
    text_like_columns: list[str] = profile["text_like_columns"]
    date_like_columns: list[str] = profile["date_like_columns"]
    categorical_columns: list[str] = profile["categorical_columns"]
    frame = load_dataset(profile["dataset_name"])

    roles: dict[str, RoleMatch] = {}

    id_column = None
    for column in columns:
        if _is_id_like_column(column, frame):
            id_column = column
            break
    if not id_column:
        for column in columns:
            series = frame[column]
            if series.nunique(dropna=True) / max(len(frame), 1) > 0.95 and _column_name_has(column, ["id", "uuid", "guid"]):
                id_column = column
                break
    roles["id_column"] = _role(id_column, 0.9 if id_column else 0.0, "id-like column detected" if id_column else "no suitable column found")

    text_column = None
    best_text_score = -1.0
    for column in text_like_columns:
        if _is_id_like_column(column, frame):
            continue
        low = column.lower()
        values = frame[column].dropna().astype(str)
        if values.empty:
            continue
        avg_len = float(values.str.len().mean())
        unique_ratio = values.nunique() / max(len(values), 1)
        name_bonus = 1.0 if _column_name_has(column, TEXT_NAME_PATTERNS) else 0.0
        if avg_len <= 20 and not name_bonus:
            continue
        score = name_bonus * 2.0 + (avg_len / 100.0) + unique_ratio
        if score > best_text_score:
            best_text_score = score
            text_column = column
    if text_column:
        reason = "column has free-text characteristics and matches text-like semantics"
        confidence = 0.9 if _column_name_has(text_column, TEXT_NAME_PATTERNS) else 0.7
        roles["text_column"] = _role(text_column, confidence, reason)
    else:
        roles["text_column"] = _role(None, 0.0, "no suitable free-text column found")

    rating_column = _best_numeric_rating_candidate(frame, numeric_columns)
    if rating_column:
        reason = "numeric score/rating-like column detected"
        confidence = 0.9 if _column_name_has(rating_column, RATING_NAME_PATTERNS) else 0.7
        roles["rating_column"] = _role(rating_column, confidence, reason)
    else:
        roles["rating_column"] = _role(None, 0.0, "no suitable column found")

    roles["target_column"] = _infer_target_column(frame, columns, categorical_columns, numeric_columns)

    date_column = None
    for column in columns:
        low = column.lower()
        if any(ex in low for ex in DATE_EXCLUDE_PATTERNS):
            continue
        series = frame[column]
        if pd.api.types.is_numeric_dtype(series):
            continue
        if _column_name_has(column, DATE_NAME_PATTERNS) and _is_date_like_series(column, series):
            date_column = column
            break
    if not date_column:
        for column in date_like_columns:
            low = column.lower()
            if any(ex in low for ex in DATE_EXCLUDE_PATTERNS):
                continue
            if pd.api.types.is_numeric_dtype(frame[column]):
                continue
            date_column = column
            break
    roles["date_column"] = _role(
        date_column,
        0.85 if date_column else 0.0,
        "date-like object/string column detected" if date_column else "no suitable column found",
    )

    version_column = None
    for preferred in ("appversion", "app_version", "version", "build"):
        for column in columns:
            if preferred in column.lower() and "previous" not in column.lower():
                version_column = column
                break
        if version_column:
            break
    roles["version_column"] = _role(
        version_column,
        0.9 if version_column else 0.0,
        "column name indicates software version" if version_column else "no suitable column found",
    )

    reply_column = next((c for c in columns if _column_name_has(c, ["reply", "response", "answer", "ответ"])), None)
    roles["reply_column"] = _role(reply_column, 0.85 if reply_column else 0.0, "reply-like column detected" if reply_column else "no suitable column found")

    reply_date_column = next((c for c in columns if _column_name_has(c, ["replied", "reply_date", "response_date", "repliedat"])), None)
    roles["reply_date_column"] = _role(
        reply_date_column,
        0.85 if reply_date_column else 0.0,
        "reply-date-like column detected" if reply_date_column else "no suitable column found",
    )

    username_column = next((c for c in columns if _column_name_has(c, ["username", "user_name", "author", "name", "пользователь"])), None)
    roles["username_column"] = _role(
        username_column,
        0.7 if username_column else 0.0,
        "username-like column detected" if username_column else "no suitable column found",
    )

    image_column = next((c for c in columns if _column_name_has(c, ["image", "avatar", "photo", "picture"])), None)
    roles["image_column"] = _role(
        image_column,
        0.8 if image_column else 0.0,
        "image-like column detected" if image_column else "no suitable column found",
    )

    return Lab3ColumnMapping(roles=roles, numeric_columns=numeric_columns, categorical_columns=categorical_columns)


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
        "Allowed role names: id_column,text_column,rating_column,target_column,date_column,version_column,reply_column,reply_date_column,username_column,image_column.\n"
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


async def get_effective_column_mapping(
    dataset_name: str,
    user_overrides: dict[str, str | None],
    use_llm_assist: bool = True,
) -> tuple[dict[str, Any], Lab3ColumnMapping, bool]:
    profile = profile_dataset(dataset_name)
    heuristic = infer_column_roles_heuristic(profile)

    llm_used = False
    mapping = heuristic
    if use_llm_assist:
        mapping = await infer_column_roles_llm(profile, heuristic)
        llm_used = True

    merged_roles = dict(mapping.roles)
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
        numeric_columns=mapping.numeric_columns,
        categorical_columns=mapping.categorical_columns,
    )
    return profile, final_mapping, llm_used
