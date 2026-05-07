import mimetypes
import json
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import HTTPException

from app.config import settings
from app.db import dumps_json, fetch_all, fetch_one, get_connection, loads_json, utcnow_iso


def _allowed_roots() -> list[Path]:
    return [Path(settings.outputs_dir).resolve(), Path(settings.datasets_dir).resolve()]


def _is_safe_path(path: Path) -> bool:
    resolved = path.resolve()
    if ".env" in resolved.name.lower() or resolved.name.startswith("."):
        return False
    for root in _allowed_roots():
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def validate_artifact_path(path: str) -> Path:
    resolved = Path(path).resolve()
    if not _is_safe_path(resolved):
        raise HTTPException(status_code=400, detail="Path is outside allowed roots.")
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Artifact file not found.")
    return resolved


def register_artifact(user_id: str, kind: str, title: str, path: str, chat_id: str | None, message_id: str | None, metadata: dict | None = None) -> dict:
    file_path = validate_artifact_path(path)
    artifact_id = str(uuid.uuid4())
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO artifacts (id, user_id, chat_id, message_id, kind, title, filename, path, mime_type, size_bytes, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                user_id,
                chat_id,
                message_id,
                kind,
                title,
                file_path.name,
                str(file_path),
                mime_type,
                file_path.stat().st_size,
                dumps_json(metadata or {}),
                utcnow_iso(),
            ),
        )
        conn.commit()
        return get_artifact(user_id, artifact_id)


def list_artifacts(user_id: str, kind: str | None = None, chat_id: str | None = None) -> list[dict]:
    query = "SELECT * FROM artifacts WHERE user_id = ?"
    params: list = [user_id]
    if kind:
        query += " AND kind = ?"
        params.append(kind)
    if chat_id:
        query += " AND chat_id = ?"
        params.append(chat_id)
    query += " ORDER BY created_at DESC"
    with get_connection() as conn:
        items = fetch_all(conn, query, tuple(params))
    return [_artifact_public(item) for item in items]


def get_artifact(user_id: str, artifact_id: str) -> dict:
    with get_connection() as conn:
        item = fetch_one(conn, "SELECT * FROM artifacts WHERE id = ? AND user_id = ?", (artifact_id, user_id))
    if not item:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return _artifact_public(item)


def _artifact_public(item: dict) -> dict:
    metadata = loads_json(item.get("metadata_json")) or {}
    return {
        "id": item["id"],
        "user_id": item["user_id"],
        "chat_id": item.get("chat_id"),
        "message_id": item.get("message_id"),
        "kind": item["kind"],
        "title": item["title"],
        "filename": item["filename"],
        "path": item["path"],
        "mime_type": item["mime_type"],
        "size_bytes": item["size_bytes"],
        "metadata": metadata,
        "created_at": item["created_at"],
        "preview_url": f"/api/artifacts/{item['id']}/preview",
        "download_url": f"/api/artifacts/{item['id']}/download",
    }


def artifact_preview(user_id: str, artifact_id: str, limit: int = 20) -> dict | str:
    artifact = get_artifact(user_id, artifact_id)
    file_path = validate_artifact_path(artifact["path"])
    mime = artifact["mime_type"]

    if mime in {"text/plain", "text/markdown", "application/json"}:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        if mime == "application/json":
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        return text
    if mime in {"text/csv", "application/vnd.ms-excel"} or file_path.suffix.lower() == ".csv":
        frame = pd.read_csv(file_path)
        return {"columns": list(frame.columns), "rows": frame.head(max(1, limit)).to_dict(orient="records")}
    if file_path.suffix.lower() in {".xlsx", ".xls"}:
        frame = pd.read_excel(file_path)
        return {"columns": list(frame.columns), "rows": frame.head(max(1, limit)).to_dict(orient="records")}
    return "binary"


def _artifact_kind_by_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return "chart"
    if suffix == ".md":
        return "report"
    if suffix == ".json":
        return "json"
    if suffix in {".csv", ".xlsx", ".xls"}:
        return "table"
    return "other"


def _collect_paths_from_result(result: dict[str, Any]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    output_files = result.get("output_files") or {}
    if isinstance(output_files, dict):
        for key, path in output_files.items():
            if isinstance(path, str) and path.strip():
                pairs.append((str(key), path))
    generated_files = result.get("generated_files") or []
    if isinstance(generated_files, list):
        for item in generated_files:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            if isinstance(path, str) and path.strip():
                title = str(item.get("title") or item.get("name") or Path(path).name)
                pairs.append((title, path))
    files = result.get("files") or []
    if isinstance(files, list):
        for item in files:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            if isinstance(path, str) and path.strip():
                title = str(item.get("title") or item.get("name") or Path(path).name)
                pairs.append((title, path))
    return pairs


def register_result_artifacts(
    user_id: str,
    result: dict[str, Any],
    *,
    chat_id: str | None,
    message_id: str | None,
    source: str = "lab3",
) -> list[dict]:
    created: list[dict] = []
    for title, path in _collect_paths_from_result(result):
        try:
            created.append(
                register_artifact(
                    user_id=user_id,
                    kind=_artifact_kind_by_path(path),
                    title=title,
                    path=path,
                    chat_id=chat_id,
                    message_id=message_id,
                    metadata={"source": source},
                )
            )
        except Exception:
            continue
    return created


def artifact_to_message_block(user_id: str, artifact: dict) -> dict:
    mime = str(artifact.get("mime_type") or "")
    kind = str(artifact.get("kind") or "")
    filename = str(artifact.get("filename") or "")
    if mime.startswith("image/"):
        return {
            "type": "chart",
            "artifact_id": artifact.get("id"),
            "title": artifact.get("title"),
            "url": artifact.get("preview_url"),
            "preview_url": artifact.get("preview_url"),
            "download_url": artifact.get("download_url"),
            "mime_type": mime,
        }

    if kind == "table" or filename.lower().endswith((".csv", ".xlsx", ".xls")):
        try:
            preview = artifact_preview(user_id, str(artifact.get("id")), limit=30)
            if isinstance(preview, dict) and "columns" in preview and "rows" in preview:
                return {
                    "type": "table",
                    "artifact_id": artifact.get("id"),
                    "title": artifact.get("title"),
                    "columns": preview.get("columns") or [],
                    "rows": preview.get("rows") or [],
                    "preview_url": artifact.get("preview_url"),
                    "download_url": artifact.get("download_url"),
                }
        except Exception:
            pass

    return {
        "type": "file",
        "artifact_id": artifact.get("id"),
        "title": artifact.get("title"),
        "filename": filename,
        "download_url": artifact.get("download_url"),
        "preview_url": artifact.get("preview_url"),
        "mime_type": mime,
    }


def register_lab3_artifacts(user_id: str, chat_id: str | None, output_files: dict[str, str] | None) -> list[dict]:
    if not output_files:
        return []
    items: list[dict] = []
    for key, path in output_files.items():
        kind = "report" if path.endswith(".md") else "json" if path.endswith(".json") else "other"
        items.append(register_artifact(user_id, kind, key, path, chat_id, None, metadata={"source": "lab3"}))
    return items
