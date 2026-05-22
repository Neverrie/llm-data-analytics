from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "llm-data-analyst-lab-backend"
    app_version: str = "0.1.0"
    datasets_dir: str = str(BASE_DIR / "datasets")
    outputs_dir: str = str(BASE_DIR / "outputs")
    cors_origins: str = "http://localhost:3003,http://127.0.0.1:3003"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8-sig",
        extra="ignore",
    )


settings = Settings()
