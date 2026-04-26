from fastapi import APIRouter

from app.schemas import Lab2DemoResponse
from app.services.lab2_service import get_lab2_demo

router = APIRouter(prefix="/lab2", tags=["lab2"])


@router.get("/demo", response_model=Lab2DemoResponse)
def lab2_demo() -> Lab2DemoResponse:
    return get_lab2_demo()

