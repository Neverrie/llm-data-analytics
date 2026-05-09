from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.schemas import DatasetsResponse
from app.services.auth_service import get_current_user
from app.services.dataset_registry import dataset_preview, dataset_profile, delete_dataset, list_datasets, upload_dataset

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("", response_model=DatasetsResponse)
def get_datasets(user: dict = Depends(get_current_user)) -> DatasetsResponse:
    return DatasetsResponse(items=list_datasets(user["id"]))


@router.post("/upload")
async def post_dataset_upload(file: UploadFile = File(...), user: dict = Depends(get_current_user)) -> dict:
    return await upload_dataset(user["id"], file)


@router.get("/{dataset_id}/preview")
def get_dataset_preview(
    dataset_id: str,
    limit: int = Query(default=20, ge=1, le=200),
    user: dict = Depends(get_current_user),
) -> dict:
    return dataset_preview(user["id"], dataset_id, limit=limit)


@router.get("/{dataset_id}/profile")
def get_dataset_profile(dataset_id: str, user: dict = Depends(get_current_user)) -> dict:
    return dataset_profile(user["id"], dataset_id)


@router.delete("/{dataset_id}")
def delete_dataset_item(dataset_id: str, user: dict = Depends(get_current_user)) -> dict:
    return delete_dataset(user["id"], dataset_id)
