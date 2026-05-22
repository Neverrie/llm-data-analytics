from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from app.services.artifact_service import artifact_preview, get_artifact, list_artifacts, register_artifact
from app.services.auth_service import get_current_user
from app.schemas import ArtifactRegisterRequest

router = APIRouter(tags=["artifacts"])


@router.get("/artifacts")
def get_artifacts(kind: str | None = None, chat_id: str | None = None, user: dict = Depends(get_current_user)):
    return {"items": list_artifacts(user["id"], kind, chat_id)}


@router.get("/artifacts/{artifact_id}")
def get_artifact_item(artifact_id: str, user: dict = Depends(get_current_user)):
    return get_artifact(user["id"], artifact_id)


@router.post("/artifacts/register")
def post_artifact(payload: ArtifactRegisterRequest, user: dict = Depends(get_current_user)):
    return register_artifact(
        user_id=user["id"],
        kind=payload.kind,
        title=payload.title,
        path=payload.path,
        chat_id=payload.chat_id,
        message_id=payload.message_id,
        metadata=payload.metadata,
    )


@router.get("/artifacts/{artifact_id}/preview")
def preview_artifact(artifact_id: str, user: dict = Depends(get_current_user)):
    content = artifact_preview(user["id"], artifact_id)
    if isinstance(content, dict):
        return JSONResponse(content=content)
    if content == "binary":
        artifact = get_artifact(user["id"], artifact_id)
        return FileResponse(path=artifact["path"], media_type=artifact["mime_type"], filename=artifact["filename"])
    return PlainTextResponse(str(content))


@router.get("/artifacts/{artifact_id}/download")
def download_artifact(artifact_id: str, user: dict = Depends(get_current_user)):
    artifact = get_artifact(user["id"], artifact_id)
    return FileResponse(path=Path(artifact["path"]), media_type=artifact["mime_type"], filename=artifact["filename"])
