from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.schemas import OllamaGenerateResponse
from app.services import lab3_agent, lab3_column_mapper


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
async def test_agent_with_mocked_ollama(lab3_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_dataset(lab3_paths / "customers_reviews.csv")

    async def fake_generate_json(self, model: str, prompt: str) -> OllamaGenerateResponse:  # noqa: ARG001
        if "Tool caller" in prompt:
            payload = {"plan": "tool caller plan", "tool_calls": [{"tool": "get_dataset_schema", "arguments": {}}, {"tool": "describe_rating", "arguments": {}}]}
        elif "critic" in prompt.lower():
            payload = {"passed": True, "issues": [], "recommendations": []}
        else:
            payload = {"plan": "planner plan", "tool_calls": [{"tool": "get_dataset_schema", "arguments": {}}, {"tool": "describe_rating", "arguments": {}}]}
        return OllamaGenerateResponse(model=model, response=json.dumps(payload, ensure_ascii=False), done=True, raw={})

    async def fake_generate_text(self, model: str, prompt: str) -> OllamaGenerateResponse:  # noqa: ARG001
        return OllamaGenerateResponse(model=model, response="Итоговый ответ на основе tools.", done=True, raw={})

    monkeypatch.setattr(lab3_agent.OllamaClient, "generate_json", fake_generate_json)
    monkeypatch.setattr(lab3_agent.OllamaClient, "generate_text", fake_generate_text)

    result = await lab3_agent.run_agent(
        dataset_name="customers_reviews.csv",
        question="Какие основные проблемы?",
        column_overrides={},
        max_tool_calls=8,
        use_critic=True,
    )
    assert result["status"] == "success"
    assert "final_answer" in result
    trace_path = Path(settings.outputs_dir) / "lab3" / "agent_trace.json"
    assert trace_path.exists()


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
