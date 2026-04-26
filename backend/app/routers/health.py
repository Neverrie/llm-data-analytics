from fastapi import APIRouter

from app.config import settings
from app.schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name)

