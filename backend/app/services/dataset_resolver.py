from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.db import fetch_one, get_connection
from app.services.lab2_service import Lab2PipelineError


class DatasetNotFoundOrForbidden(Lab2PipelineError):
    def __init__(self, message: str = "Датасет не найден или недоступен. Возможно, файл был удалён или выбран датасет другого пользователя."):
        super().__init__(message=message, status_code=404)


@dataclass
class ResolvedDataset:
    dataset_id: str | None
    name: str
    filename: str
    path: Path
    visibility: str
    owner_user_id: str | None


def _safe_ref(value: str) -> str:
    cleaned = (value or "").strip().replace("\\", "/")
    if not cleaned:
        raise Lab2PipelineError("Dataset reference is required.", status_code=400)
    if ".." in cleaned:
        raise Lab2PipelineError("Invalid dataset reference.", status_code=400)
    return cleaned.lstrip("/")


def _public_fallback(ref: str) -> ResolvedDataset:
    base = Path(settings.datasets_dir).resolve()
    candidate = (base / ref).resolve()
    if base not in candidate.parents and candidate != base:
        raise Lab2PipelineError("Invalid dataset path.", status_code=400)
    if not candidate.exists() or not candidate.is_file():
        raise DatasetNotFoundOrForbidden()
    return ResolvedDataset(
        dataset_id=None,
        name=ref,
        filename=candidate.name,
        path=candidate,
        visibility="public",
        owner_user_id=None,
    )


def resolve_dataset_for_user(dataset_name_or_id: str, user_id: str | None) -> ResolvedDataset:
    ref = _safe_ref(dataset_name_or_id)
    with get_connection() as conn:
        row = None
        if user_id:
            row = fetch_one(
                conn,
                (
                    "SELECT * FROM datasets WHERE id = ? AND (user_id IS NULL OR user_id = ?) "
                    "ORDER BY CASE WHEN user_id = ? THEN 0 ELSE 1 END, created_at DESC LIMIT 1"
                ),
                (ref, user_id, user_id),
            )
        else:
            row = fetch_one(conn, "SELECT * FROM datasets WHERE id = ? AND user_id IS NULL LIMIT 1", (ref,))

        if row is None:
            if user_id:
                row = fetch_one(
                    conn,
                    (
                        "SELECT * FROM datasets WHERE name = ? AND (user_id IS NULL OR user_id = ?) "
                        "ORDER BY CASE WHEN user_id = ? THEN 0 ELSE 1 END, created_at DESC LIMIT 1"
                    ),
                    (ref, user_id, user_id),
                )
            else:
                row = fetch_one(
                    conn,
                    "SELECT * FROM datasets WHERE name = ? AND user_id IS NULL ORDER BY created_at DESC LIMIT 1",
                    (ref,),
                )

    if row is not None:
        path = Path(str(row["path"])).resolve()
        if not path.exists() or not path.is_file():
            raise DatasetNotFoundOrForbidden()
        owner = row["user_id"]
        return ResolvedDataset(
            dataset_id=str(row["id"]),
            name=str(row["name"]),
            filename=path.name,
            path=path,
            visibility="private" if owner else "public",
            owner_user_id=owner,
        )

    return _public_fallback(ref)
