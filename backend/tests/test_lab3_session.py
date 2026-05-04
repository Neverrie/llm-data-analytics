from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import lab3_agent
from app.services.lab3_session import append_turn, build_context_for_followup, create_session_id, load_session, reset_session


@pytest.fixture
def session_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    datasets_dir = tmp_path / "datasets"
    outputs_dir = tmp_path / "outputs"
    datasets_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "datasets_dir", str(datasets_dir))
    monkeypatch.setattr(settings, "outputs_dir", str(outputs_dir))
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_api_key", "test")

    frame = pd.DataFrame(
        [
            {"content": "Bad payment", "score": 1, "at": "2024-01-01", "appVersion": "1.0", "replyContent": None, "repliedAt": None},
            {"content": "Great", "score": 5, "at": "2024-01-02", "appVersion": "1.0", "replyContent": "Thanks", "repliedAt": "2024-01-03"},
        ]
    )
    frame.to_csv(datasets_dir / "customers_reviews.csv", index=False)
    return datasets_dir


def test_session_create_save_load(session_paths: Path) -> None:
    session_id = create_session_id()
    append_turn(
        session_id=session_id,
        user_question="Q1",
        agent_answer="A1",
        tool_summary=["get_dataset_schema"],
        column_mapping={"roles": {}},
        dataset_name="customers_reviews.csv",
        key_findings=["f1"],
    )
    loaded = load_session(session_id)
    assert loaded is not None
    assert len(loaded.get("turns", [])) == 1


def test_session_context_followup(session_paths: Path) -> None:
    session_id = create_session_id()
    append_turn(
        session_id=session_id,
        user_question="Q1",
        agent_answer="A1",
        tool_summary=["get_dataset_schema"],
        column_mapping={"roles": {}},
        dataset_name="customers_reviews.csv",
        key_findings=["f1"],
    )
    context = build_context_for_followup(session_id, "customers_reviews.csv")
    assert context["history_length"] >= 1


@pytest.mark.asyncio
async def test_lab3_ask_returns_session_id(session_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001,ARG001
        if purpose == "planner":
            return json.dumps({"plan": "planner", "tool_calls": [{"tool": "get_dataset_schema", "arguments": {}}]})
        return "## Краткий ответ\nТест"

    monkeypatch.setattr(lab3_agent.LLMClient, "chat", fake_chat)

    client = TestClient(app)
    response = client.post(
        "/api/lab3/ask",
        json={
            "dataset_name": "customers_reviews.csv",
            "question": "Сделай обзор",
            "column_overrides": {},
            "max_tool_calls": 4,
            "use_critic": False,
            "analysis_mode": "balanced",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("session_id")


def test_reset_session_endpoint(session_paths: Path) -> None:
    session_id = create_session_id()
    append_turn(
        session_id=session_id,
        user_question="Q",
        agent_answer="A",
        tool_summary=["x"],
        column_mapping={"roles": {}},
        dataset_name="customers_reviews.csv",
        key_findings=["f"],
    )

    client = TestClient(app)
    response = client.post("/api/lab3/reset-session", json={"session_id": session_id})
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    reset_session(session_id)
