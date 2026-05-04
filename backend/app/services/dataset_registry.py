import re
import uuid
from pathlib import Path

import pandas as pd
from fastapi import HTTPException, UploadFile

from app.config import settings
from app.db import fetch_all, fetch_one, get_connection, utcnow_iso

_ALLOWED_SUFFIXES = {".csv", ".xlsx", ".xls"}
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")
MAX_UPLOAD_SIZE_BYTES = 20 * 1024 * 1024


def _safe_filename(name: str) -> str:
    base = Path(name).name.replace(" ", "_")
    safe = _SAFE_FILENAME_RE.sub("_", base)
    safe = safe.strip("._") or "dataset"
    return safe


def _read_df(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    return pd.read_excel(path)


def _register_if_missing(path: Path, source: str, user_id: str | None = None, original_filename: str | None = None) -> None:
    with get_connection() as conn:
        existing = fetch_one(conn, "SELECT id FROM datasets WHERE path = ?", (str(path.resolve()),))
        if existing:
            return
        try:
            frame = _read_df(path)
            rows_count = int(len(frame))
            columns_count = int(len(frame.columns))
        except Exception:
            rows_count = None
            columns_count = None
        conn.execute(
            "INSERT INTO datasets (id, user_id, name, original_filename, path, source, rows_count, columns_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                user_id,
                path.name,
                original_filename or path.name,
                str(path.resolve()),
                source,
                rows_count,
                columns_count,
                utcnow_iso(),
            ),
        )
        conn.commit()


def sync_builtin_datasets() -> None:
    root = Path(settings.datasets_dir)
    root.mkdir(parents=True, exist_ok=True)
    for path in root.glob("*"):
        if path.is_file() and path.suffix.lower() in _ALLOWED_SUFFIXES:
            _register_if_missing(path, "built_in")


def list_datasets(user_id: str) -> list[dict]:
    sync_builtin_datasets()
    with get_connection() as conn:
        rows = fetch_all(
            conn,
            "SELECT * FROM datasets WHERE user_id IS NULL OR user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "source": row["source"],
            "rows_count": row["rows_count"],
            "columns_count": row["columns_count"],
            "created_at": row["created_at"],
            "preview_available": True,
        }
        for row in rows
    ]


def get_dataset_for_user(user_id: str, dataset_id: str) -> dict:
    with get_connection() as conn:
        item = fetch_one(conn, "SELECT * FROM datasets WHERE id = ? AND (user_id IS NULL OR user_id = ?)", (dataset_id, user_id))
    if not item:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return item


def dataset_preview(user_id: str, dataset_id: str, limit: int = 20) -> dict:
    item = get_dataset_for_user(user_id, dataset_id)
    frame = _read_df(Path(item["path"]))
    return {"columns": list(frame.columns), "rows": frame.head(max(1, limit)).to_dict(orient="records")}


def dataset_profile(user_id: str, dataset_id: str) -> dict:
    item = get_dataset_for_user(user_id, dataset_id)
    frame = _read_df(Path(item["path"]))
    cols = []
    for col in frame.columns:
        series = frame[col]
        cols.append(
            {
                "name": str(col),
                "dtype": str(series.dtype),
                "missing_count": int(series.isna().sum()),
                "unique_count": int(series.nunique(dropna=True)),
            }
        )
    return {"rows_count": int(len(frame)), "columns_count": int(len(frame.columns)), "columns": cols}


async def upload_dataset(user_id: str, file: UploadFile) -> dict:
    original_name = file.filename or "dataset.csv"
    safe_name = _safe_filename(original_name)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="Unsupported file extension.")
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File is too large. Max size is 20 MB.")

    user_dir = Path(settings.outputs_dir) / "users" / user_id / "datasets"
    user_dir.mkdir(parents=True, exist_ok=True)
    output_path = user_dir / safe_name
    if output_path.exists():
        output_path = user_dir / f"{Path(safe_name).stem}_{uuid.uuid4().hex[:8]}{suffix}"
    output_path.write_bytes(content)

    try:
        frame = _read_df(output_path)
    except Exception as exc:
        output_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Uploaded file cannot be parsed: {exc}") from exc

    dataset_id = str(uuid.uuid4())
    now = utcnow_iso()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO datasets (id, user_id, name, original_filename, path, source, rows_count, columns_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                dataset_id,
                user_id,
                output_path.name,
                original_name,
                str(output_path.resolve()),
                "upload",
                int(len(frame)),
                int(len(frame.columns)),
                now,
            ),
        )
        conn.commit()
    return {
        "id": dataset_id,
        "name": output_path.name,
        "source": "upload",
        "rows_count": int(len(frame)),
        "columns_count": int(len(frame.columns)),
        "created_at": now,
        "preview_available": True,
    }


def datasets_for_lab3() -> list[dict]:
    sync_builtin_datasets()
    with get_connection() as conn:
        rows = fetch_all(conn, "SELECT name, path, source FROM datasets ORDER BY created_at DESC")
    seen: set[str] = set()
    out: list[dict] = []
    for row in rows:
        name = row["name"]
        if name in seen:
            continue
        seen.add(name)
        ext = Path(name).suffix.lower().lstrip(".") or "file"
        out.append({"name": name, "path": row["path"], "type": ext})
    return out
