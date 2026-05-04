from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "llm-data-analyst-lab-backend"
    app_version: str = "0.1.0"
    llm_provider: str = "openrouter"
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openai/gpt-oss-120b:free"
    openrouter_fallback_models: str = "openai/gpt-oss-20b:free"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen3:8b"
    datasets_dir: str = str(BASE_DIR / "datasets")
    outputs_dir: str = str(BASE_DIR / "outputs")
    lab2_dataset_filename: str = "customer_reviews"
    lab3_planner_model: str = "qwen3:8b"
    lab3_tool_caller_model: str = "qwen2.5-coder:7b"
    lab3_critic_model: str = "deepseek-r1:8b"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()


def get_default_model_for_provider(provider: str | None = None) -> str:
    resolved_provider = (provider or settings.llm_provider or "").strip().lower()
    if resolved_provider == "openrouter":
        return settings.openrouter_model
    return settings.ollama_model


def get_lab2_model() -> str:
    return get_default_model_for_provider()


def get_lab3_model() -> str:
    return get_default_model_for_provider()

