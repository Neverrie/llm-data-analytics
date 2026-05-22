from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db
from app.routers.artifacts import router as artifacts_router
from app.routers.auth import router as auth_router
from app.routers.datasets import router as datasets_router
from app.routers.health import router as health_router
from app.routers.workspace import router as workspace_router
from app.services.auth_service import ensure_demo_user

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
    init_db()
    ensure_demo_user()


app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(workspace_router, prefix="/api")
app.include_router(datasets_router, prefix="/api")
app.include_router(artifacts_router, prefix="/api")
