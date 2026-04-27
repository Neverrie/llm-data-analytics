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
from app.services.lab3_session import append_turn, build_context_for_followup, create_session_id, load_session


@pytest.fixture
def session_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    datasets_dir = tmp_path / "datasets"
    outputs_dir = tmp_path / "outputs"
    datasets_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "datasets_dir", str(datasets_dir))
    monkeypatch.setattr(settings, "outputs_dir", str(outputs_dir))
    return datasets_dir


def _write_dataset(path: Path) -> None:
    frame = pd.DataFrame(
        [
            {"content": "Bad payment flow", "score": 1, "at": "2024-01-01 10:00:00", "appVersion": "1.0"},
            {"content": "Great app", "score": 5, "at": "2024-01-02 10:00:00", "appVersion": "1.1"},
        ]
    )
    frame.to_csv(path, index=False)


def test_session_create_save_load() -> None:
    sid = create_session_id()
    append_turn(
        session_id=sid,
        user_question="Первый вопрос",
        agent_answer="Первый ответ",
        tool_summary=["get_dataset_schema (success)"],
        column_mapping={"roles": {}},
        dataset_name="customers_reviews.csv",
        key_findings=["rows and columns read"],
    )
    state = load_session(sid)
    assert state is not None
    assert state["session_id"] == sid
    assert len(state["turns"]) == 1


def test_session_context_followup(session_paths: Path) -> None:
    sid = create_session_id()
    state = append_turn(
        session_id=sid,
        user_question="Сделай обзор",
        agent_answer="Краткий ответ по данным",
        tool_summary=["get_dataset_schema (success)"],
        column_mapping={"roles": {"text_column": {"column": "content"}}},
        dataset_name="customers_reviews.csv",
        key_findings=["schema ok"],
    )
    loaded = load_session(sid)
    assert loaded is not None
    assert len(loaded.get("turns", [])) == 1
    assert state.get("conversation_summary")
    context = build_context_for_followup(sid, "customers_reviews.csv")
    assert context["history_length"] == 1
    assert "Вопрос" in context["conversation_summary"]


@pytest.mark.asyncio
async def test_lab3_ask_returns_session_id(session_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_dataset(session_paths / "customers_reviews.csv")

    async def fake_generate_json(self, model: str, prompt: str) -> OllamaGenerateResponse:  # noqa: ARG001
        payload = {"plan": "planner plan", "tool_calls": [{"tool": "get_dataset_schema", "arguments": {}}]}
        return OllamaGenerateResponse(model=model, response=json.dumps(payload), done=True, raw={})

    async def fake_generate_text(self, model: str, prompt: str) -> OllamaGenerateResponse:  # noqa: ARG001
        return OllamaGenerateResponse(model=model, response="## Краткий ответ\nТест", done=True, raw={})

    monkeypatch.setattr(lab3_agent.OllamaClient, "generate_json", fake_generate_json)
    monkeypatch.setattr(lab3_agent.OllamaClient, "generate_text", fake_generate_text)

    client = TestClient(app)
    response = client.post(
        "/api/lab3/ask",
        json={
            "dataset_name": "customers_reviews.csv",
            "question": "Сделай краткий обзор",
            "column_overrides": {},
            "max_tool_calls": 4,
            "use_critic": False,
            "analysis_mode": "balanced",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"]
    assert payload["history_length"] >= 1


def test_reset_session_endpoint(session_paths: Path) -> None:
    sid = create_session_id()
    append_turn(
        session_id=sid,
        user_question="Q",
        agent_answer="A",
        tool_summary=["get_dataset_schema (success)"],
        column_mapping={"roles": {}},
        dataset_name="customers_reviews.csv",
        key_findings=["ok"],
    )
    client = TestClient(app)
    response = client.post("/api/lab3/reset-session", json={"session_id": sid})
    assert response.status_code == 200
    loaded = load_session(sid)
    assert loaded is not None
    assert loaded.get("turns") == []
