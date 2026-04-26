from fastapi import APIRouter

from app.schemas import Lab1StatusResponse
from app.services.lab1_service import get_lab1_status

router = APIRouter(prefix="/lab1", tags=["lab1"])


@router.get("/status", response_model=Lab1StatusResponse)
def lab1_status() -> Lab1StatusResponse:
    return get_lab1_status()

