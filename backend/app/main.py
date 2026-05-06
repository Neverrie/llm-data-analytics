from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import health, lab1, lab2, lab3
from app.routers.artifacts import router as artifacts_router
from app.routers.auth import router as auth_router
from app.routers.datasets import router as datasets_router
from app.routers.workspace import router as workspace_router
from app.services.auth_service import ensure_demo_user
from app.services.dataset_registry import sync_builtin_datasets

app = FastAPI(title=settings.app_name, version=settings.app_version)
cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    ensure_demo_user()
    sync_builtin_datasets()


app.include_router(health.router, prefix="/api")
app.include_router(lab1.router, prefix="/api")
app.include_router(lab2.router, prefix="/api")
app.include_router(lab3.router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(workspace_router, prefix="/api")
app.include_router(datasets_router, prefix="/api")
app.include_router(artifacts_router, prefix="/api")
