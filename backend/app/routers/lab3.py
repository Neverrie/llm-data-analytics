from fastapi import APIRouter

from app.schemas import Lab3StatusResponse
from app.services.lab3_service import get_lab3_status

router = APIRouter(prefix="/lab3", tags=["lab3"])


@router.get("/status", response_model=Lab3StatusResponse)
def lab3_status() -> Lab3StatusResponse:
    return get_lab3_status()

