from pathlib import Path
import uuid

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.config import settings
from app.db import fetch_all, fetch_one, get_connection, utcnow_iso
from app.services.auth_service import get_current_user

router = APIRouter(tags=["datasets"])


@router.get("/datasets")
def list_datasets(user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        rows = fetch_all(
            conn,
            "SELECT * FROM datasets WHERE user_id = ? OR user_id IS NULL ORDER BY created_at DESC",
            (user["id"],),
        )
    items = [
        {
            "id": r["id"],
            "name": r["name"],
            "source": r["source"],
            "filename": r["original_filename"],
            "owner_user_id": r["user_id"],
            "rows_count": r.get("rows_count"),
            "columns_count": r.get("columns_count"),
            "created_at": r["created_at"],
            "preview_available": True,
        }
        for r in rows
    ]
    return {"items": items}


@router.post("/datasets/upload")
async def upload_dataset(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    datasets_dir = Path(settings.datasets_dir)
    datasets_dir.mkdir(parents=True, exist_ok=True)
    dataset_id = str(uuid.uuid4())
    target = datasets_dir / f"{dataset_id}_{file.filename}"
    data = await file.read()
    target.write_bytes(data)

    rows_count = None
    columns_count = None
    try:
        if target.suffix.lower() == ".csv":
            df = pd.read_csv(target)
        else:
            df = pd.read_excel(target)
        rows_count = int(df.shape[0])
        columns_count = int(df.shape[1])
    except Exception:
        pass

    name = file.filename or target.name
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO datasets (id, user_id, name, original_filename, path, source, rows_count, columns_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (dataset_id, user["id"], name, file.filename or name, str(target), "uploaded", rows_count, columns_count, utcnow_iso()),
        )
        conn.commit()

    return {
        "id": dataset_id,
        "name": name,
        "source": "uploaded",
        "filename": file.filename or name,
        "owner_user_id": user["id"],
        "rows_count": rows_count,
        "columns_count": columns_count,
        "created_at": utcnow_iso(),
        "preview_available": True,
    }


@router.delete("/datasets/{dataset_id}")
def delete_dataset(dataset_id: str, user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        ds = fetch_one(conn, "SELECT * FROM datasets WHERE id = ? AND user_id = ?", (dataset_id, user["id"]))
        if not ds:
            raise HTTPException(status_code=404, detail="Dataset not found")
        conn.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
        conn.commit()

    try:
        Path(ds["path"]).unlink(missing_ok=True)
    except Exception:
        pass

    return {"status": "deleted", "id": dataset_id}


@router.get("/datasets/{dataset_id}/preview")
def preview_dataset(dataset_id: str, limit: int = 20, user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        ds = fetch_one(conn, "SELECT * FROM datasets WHERE id = ? AND (user_id = ? OR user_id IS NULL)", (dataset_id, user["id"]))
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    path = Path(ds["path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dataset file not found")

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)
    return {"columns": list(df.columns), "rows": df.head(max(1, limit)).to_dict(orient="records")}


@router.get("/datasets/{dataset_id}/profile")
def profile_dataset(dataset_id: str, user: dict = Depends(get_current_user)):
    with get_connection() as conn:
        ds = fetch_one(conn, "SELECT * FROM datasets WHERE id = ? AND (user_id = ? OR user_id IS NULL)", (dataset_id, user["id"]))
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    path = Path(ds["path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Dataset file not found")

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)

    columns = []
    for col in df.columns:
        series = df[col]
        columns.append(
            {
                "name": str(col),
                "dtype": str(series.dtype),
                "missing_count": int(series.isna().sum()),
                "unique_count": int(series.nunique(dropna=True)),
            }
        )
    return {"rows_count": int(df.shape[0]), "columns_count": int(df.shape[1]), "columns": columns}
