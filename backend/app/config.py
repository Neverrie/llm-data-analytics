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
    lab3_model: str | None = None
    openrouter_fallback_models: str = "openai/gpt-oss-20b:free"
    openrouter_timeout_seconds: int = 60
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen3:8b"
    datasets_dir: str = str(BASE_DIR / "datasets")
    outputs_dir: str = str(BASE_DIR / "outputs")
    host_outputs_dir: str | None = None
    host_datasets_dir: str | None = None
    lab2_dataset_filename: str = "customer_reviews"
    lab3_planner_model: str = "qwen3:8b"
    lab3_tool_caller_model: str = "qwen2.5-coder:7b"
    lab3_critic_model: str = "deepseek-r1:8b"
    lab3_code_exec_timeout_seconds: int = 15
    lab3_code_interpreter_engine: str = "tool_calling"
    sandbox_runner_mode: str = "docker"
    sandbox_docker_image: str = "llm-data-analytics-sandbox:latest"
    sandbox_docker_user: str = "1000:1000"
    sandbox_allow_root_retry: bool = False
    lab3_code_interpreter_max_total_seconds: int = 180
    lab3_code_interpreter_hard_max_steps: int = 12
    lab3_code_interpreter_auto_inspect: bool = True
    cors_origins: str = "http://localhost:3003,http://127.0.0.1:3003,http://82.162.61.44:3003"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8-sig",
        extra="ignore",
    )


settings = Settings()


def get_default_model_for_provider(provider: str | None = None) -> str:
    resolved_provider = (provider or settings.llm_provider or "").strip().lower()
    if resolved_provider == "openrouter":
        return settings.openrouter_model
    if resolved_provider == "gemini":
        return settings.gemini_model
    return settings.ollama_model


def get_lab2_model() -> str:
    return get_default_model_for_provider()


def get_lab3_model() -> str:
    if (settings.lab3_model or "").strip():
        return str(settings.lab3_model).strip()
    return get_default_model_for_provider()

