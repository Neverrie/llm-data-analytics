from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "llm-data-analyst-lab-backend"
    app_version: str = "0.1.0"

    llm_provider: str = "openrouter"
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str | None = None

    sandbox_docker_image: str = "llm-data-analytics-sandbox:latest"
    sandbox_docker_user: str = "1000:1000"
    sandbox_allow_network: bool = False
    sandbox_python_userbase_dir: str = "/outputs/.sandbox_userbase"
    sandbox_pip_cache_dir: str = "/outputs/.sandbox_pip_cache"

    host_outputs_dir: str | None = None
    host_datasets_dir: str | None = None

    outputs_dir: str = "/outputs"
    datasets_dir: str = "/datasets"

    cors_origins: str = "http://localhost:3003,http://127.0.0.1:3003"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8-sig",
        extra="ignore",
    )


settings = Settings()
