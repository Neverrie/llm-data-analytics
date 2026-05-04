from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from app.schemas import ArtifactRegisterRequest, ArtifactsResponse
from app.services.artifact_service import artifact_preview, get_artifact, list_artifacts, register_artifact, validate_artifact_path
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("", response_model=ArtifactsResponse)
def get_artifacts(
    kind: str | None = Query(default=None),
    chat_id: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
) -> ArtifactsResponse:
    return ArtifactsResponse(items=list_artifacts(user["id"], kind=kind, chat_id=chat_id))


@router.get("/{artifact_id}")
def get_artifact_metadata(artifact_id: str, user: dict = Depends(get_current_user)) -> dict:
    return get_artifact(user["id"], artifact_id)


@router.get("/{artifact_id}/download")
def download_artifact(artifact_id: str, user: dict = Depends(get_current_user)) -> FileResponse:
    artifact = get_artifact(user["id"], artifact_id)
    path = validate_artifact_path(artifact["path"])
    return FileResponse(path, media_type=artifact["mime_type"], filename=artifact["filename"])


@router.get("/{artifact_id}/preview")
def preview_artifact(
    artifact_id: str,
    limit: int = Query(default=20, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    artifact = get_artifact(user["id"], artifact_id)
    path = validate_artifact_path(artifact["path"])
    mime = artifact["mime_type"]

    if mime in {"image/png", "image/jpeg", "image/webp"}:
        return FileResponse(path, media_type=mime, filename=Path(artifact["filename"]).name)

    preview = artifact_preview(user["id"], artifact_id, limit=limit)
    if isinstance(preview, dict) or isinstance(preview, list):
        return JSONResponse(content=preview)
    if preview == "binary":
        return JSONResponse(content={"detail": "No inline preview for this file type."})
    return PlainTextResponse(preview)


@router.post("/register")
def post_register_artifact(payload: ArtifactRegisterRequest, user: dict = Depends(get_current_user)) -> dict:
    return register_artifact(
        user_id=user["id"],
        kind=payload.kind,
        title=payload.title,
        path=payload.path,
        chat_id=payload.chat_id,
        message_id=payload.message_id,
        metadata=payload.metadata,
    )
