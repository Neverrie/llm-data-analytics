from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "llm-data-analyst-lab-backend"
    app_version: str = "0.1.0"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen3:8b"
    datasets_dir: str = str(BASE_DIR / "datasets")
    outputs_dir: str = str(BASE_DIR / "outputs")
    lab2_dataset_filename: str = "customer_reviews"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()

