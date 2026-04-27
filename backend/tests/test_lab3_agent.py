from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.schemas import OllamaGenerateResponse
from app.services import lab3_agent


@pytest.fixture
def lab3_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    datasets_dir = tmp_path / "datasets"
    outputs_dir = tmp_path / "outputs"
    datasets_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "datasets_dir", str(datasets_dir))
    monkeypatch.setattr(settings, "outputs_dir", str(outputs_dir))
    monkeypatch.setattr(settings, "lab3_planner_model", "qwen3:8b")
    monkeypatch.setattr(settings, "lab3_tool_caller_model", "qwen2.5-coder:7b")
    monkeypatch.setattr(settings, "lab3_critic_model", "deepseek-r1:8b")
    return datasets_dir


def _write_dataset(path: Path) -> None:
    frame = pd.DataFrame(
        [
            {
                "content": "Bad payment flow",
                "score": 1,
                "at": "2024-01-01 10:00:00",
                "appVersion": "1.0",
                "replyContent": None,
                "repliedAt": None,
            },
            {
                "content": "Great app",
                "score": 5,
                "at": "2024-01-02 10:00:00",
                "appVersion": "1.0",
                "replyContent": "Thanks",
                "repliedAt": "2024-01-03 10:00:00",
            },
        ]
    )
    frame.to_csv(path, index=False)


@pytest.mark.asyncio
async def test_fast_mode_no_planner_llm_and_no_critic(lab3_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_dataset(lab3_paths / "customers_reviews.csv")

    async def fail_generate_json(self, model: str, prompt: str) -> OllamaGenerateResponse:  # noqa: ARG001
        raise AssertionError("fast mode should not call generate_json")

    async def fake_generate_text(self, model: str, prompt: str) -> OllamaGenerateResponse:  # noqa: ARG001
        return OllamaGenerateResponse(model=model, response="Финальный ответ", done=True, raw={})

    monkeypatch.setattr(lab3_agent.OllamaClient, "generate_json", fail_generate_json)
    monkeypatch.setattr(lab3_agent.OllamaClient, "generate_text", fake_generate_text)

    result = await lab3_agent.run_agent(
        dataset_name="customers_reviews.csv",
        question="Сделай краткий обзор датасета",
        column_overrides={},
        max_tool_calls=6,
        use_critic=True,
        analysis_mode="fast",
    )
    assert result["status"] == "success"
    assert result["analysis_mode"] == "fast"
    assert result["llm_calls_count"] <= 1
    assert any("Critic skipped in fast mode" in warning for warning in result["warnings"])


@pytest.mark.asyncio
async def test_balanced_mode_calls_planner(lab3_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_dataset(lab3_paths / "customers_reviews.csv")
    calls = {"json": 0}

    async def fake_generate_json(self, model: str, prompt: str) -> OllamaGenerateResponse:  # noqa: ARG001
        calls["json"] += 1
        payload = {"plan": "planner plan", "tool_calls": [{"tool": "get_dataset_schema", "arguments": {}}, {"tool": "describe_rating", "arguments": {}}]}
        return OllamaGenerateResponse(model=model, response=json.dumps(payload, ensure_ascii=False), done=True, raw={})

    async def fake_generate_text(self, model: str, prompt: str) -> OllamaGenerateResponse:  # noqa: ARG001
        return OllamaGenerateResponse(model=model, response="Финальный ответ", done=True, raw={})

    monkeypatch.setattr(lab3_agent.OllamaClient, "generate_json", fake_generate_json)
    monkeypatch.setattr(lab3_agent.OllamaClient, "generate_text", fake_generate_text)

    result = await lab3_agent.run_agent(
        dataset_name="customers_reviews.csv",
        question="Какие ключевые метрики?",
        column_overrides={},
        max_tool_calls=6,
        use_critic=False,
        analysis_mode="balanced",
    )
    assert result["status"] == "success"
    assert calls["json"] >= 1


@pytest.mark.asyncio
async def test_max_tool_calls_respected(lab3_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_dataset(lab3_paths / "customers_reviews.csv")

    async def fake_generate_json(self, model: str, prompt: str) -> OllamaGenerateResponse:  # noqa: ARG001
        payload = {
            "plan": "planner plan",
            "tool_calls": [
                {"tool": "get_dataset_schema", "arguments": {}},
                {"tool": "get_missing_values_report", "arguments": {}},
                {"tool": "describe_numeric_columns", "arguments": {}},
                {"tool": "get_rating_distribution", "arguments": {}},
            ],
        }
        return OllamaGenerateResponse(model=model, response=json.dumps(payload, ensure_ascii=False), done=True, raw={})

    async def fake_generate_text(self, model: str, prompt: str) -> OllamaGenerateResponse:  # noqa: ARG001
        return OllamaGenerateResponse(model=model, response="ok", done=True, raw={})

    monkeypatch.setattr(lab3_agent.OllamaClient, "generate_json", fake_generate_json)
    monkeypatch.setattr(lab3_agent.OllamaClient, "generate_text", fake_generate_text)

    result = await lab3_agent.run_agent(
        dataset_name="customers_reviews.csv",
        question="Сделай отчёт",
        column_overrides={},
        max_tool_calls=2,
        use_critic=False,
        analysis_mode="balanced",
    )
    assert len(result["planner_output"]["tool_calls"]) <= 2


def test_lab3_status_endpoint(lab3_paths: Path) -> None:
    _write_dataset(lab3_paths / "customers_reviews.csv")
    client = TestClient(app)
    response = client.get("/api/lab3/status")
    assert response.status_code == 200


def test_lab3_profile_endpoint(lab3_paths: Path) -> None:
    _write_dataset(lab3_paths / "customers_reviews.csv")
    client = TestClient(app)
    response = client.get("/api/lab3/profile?dataset_name=customers_reviews.csv")
    assert response.status_code == 200
    assert "column_mapping" in response.json()


def test_lab3_tools_endpoint(lab3_paths: Path) -> None:
    _write_dataset(lab3_paths / "customers_reviews.csv")
    client = TestClient(app)
    response = client.get("/api/lab3/tools")
    assert response.status_code == 200
    assert "tools" in response.json()


def test_upload_rejects_unsupported_extension(lab3_paths: Path) -> None:
    client = TestClient(app)
    response = client.post(
        "/api/lab3/upload-dataset",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


def test_upload_secure_filename_no_traversal(lab3_paths: Path) -> None:
    client = TestClient(app)
    response = client.post(
        "/api/lab3/upload-dataset",
        files={"file": ("../../evil file.csv", b"a,b\n1,2\n", "text/csv")},
    )
    assert response.status_code == 200
    dataset_name = response.json()["dataset"]["name"]
    assert ".." not in dataset_name
    assert "uploads/" in dataset_name
