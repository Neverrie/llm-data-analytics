from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import lab3_agent


@pytest.fixture
def lab3_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    datasets_dir = tmp_path / "datasets"
    outputs_dir = tmp_path / "outputs"
    datasets_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "datasets_dir", str(datasets_dir))
    monkeypatch.setattr(settings, "outputs_dir", str(outputs_dir))
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_api_key", "test")
    monkeypatch.setattr(settings, "openrouter_model", "openai/gpt-oss-120b:free")
    return datasets_dir


def _write_dataset(path: Path) -> None:
    frame = pd.DataFrame(
        [
            {"content": "Bad payment flow", "score": 1, "at": "2024-01-01 10:00:00", "appVersion": "1.0", "replyContent": None, "repliedAt": None},
            {"content": "Great app", "score": 5, "at": "2024-01-02 10:00:00", "appVersion": "1.0", "replyContent": "Thanks", "repliedAt": "2024-01-03 10:00:00"},
        ]
    )
    frame.to_csv(path, index=False)


def test_parse_planner_output_plain_json() -> None:
    data = lab3_agent.parse_planner_output('{"plan":"x","tool_calls":[{"tool":"get_dataset_schema","arguments":{}}]}')
    assert data["plan"] == "x"


def test_parse_planner_output_fenced_json() -> None:
    data = lab3_agent.parse_planner_output("""```json
{"plan":"x","tool_calls":[{"tool":"get_dataset_schema","arguments":{}}]}
```""")
    assert data["tool_calls"][0]["tool"] == "get_dataset_schema"


def test_parse_planner_output_with_prefix_text() -> None:
    text = 'Planner response:\n{"plan":"x","tool_calls":[{"tool":"get_dataset_schema","arguments":{}}]} trailing'
    data = lab3_agent.parse_planner_output(text)
    assert data["plan"] == "x"


def test_parse_planner_output_truncated_fallback() -> None:
    with pytest.raises(Exception):
        lab3_agent.parse_planner_output('{"plan":"x","tool_calls":[{"tool":"get_dataset_schema","arguments":{}}')


def test_parse_critic_output_russian_json() -> None:
    parsed = lab3_agent.parse_critic_output('{"passed":true,"issues":[],"recommendations":["Уточнить"]}')
    assert parsed["passed"] is True


def test_critic_prompt_does_not_require_final_answer_json() -> None:
    prompt = lab3_agent.build_critic_prompt("Q", {"roles": {}}, [], "A")
    assert "Не требуй, чтобы final answer был JSON" in prompt


@pytest.mark.asyncio
async def test_fast_mode_no_planner_llm_and_no_critic(lab3_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_dataset(lab3_paths / "customers_reviews.csv")

    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001,ARG001
        if purpose == "final_answer":
            return "Финальный ответ"
        raise AssertionError("fast mode should not call planner/critic chat")

    monkeypatch.setattr(lab3_agent.LLMClient, "chat", fake_chat)

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
    assert any("Critic skipped in fast mode" in warning for warning in result["warnings"])


@pytest.mark.asyncio
async def test_balanced_mode_calls_planner(lab3_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_dataset(lab3_paths / "customers_reviews.csv")
    calls = {"count": 0}

    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001,ARG001
        calls["count"] += 1
        if purpose == "planner":
            return json.dumps({"plan": "planner plan", "tool_calls": [{"tool": "get_dataset_schema", "arguments": {}}]})
        return "Финальный ответ"

    monkeypatch.setattr(lab3_agent.LLMClient, "chat", fake_chat)

    result = await lab3_agent.run_agent(
        dataset_name="customers_reviews.csv",
        question="Какие ключевые метрики?",
        column_overrides={},
        max_tool_calls=6,
        use_critic=False,
        analysis_mode="balanced",
    )
    assert result["status"] == "success"
    assert calls["count"] >= 2


@pytest.mark.asyncio
async def test_max_tool_calls_respected(lab3_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_dataset(lab3_paths / "customers_reviews.csv")

    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001,ARG001
        if purpose == "planner":
            return json.dumps(
                {
                    "plan": "planner plan",
                    "tool_calls": [
                        {"tool": "get_dataset_schema", "arguments": {}},
                        {"tool": "get_missing_values_report", "arguments": {}},
                        {"tool": "describe_numeric_columns", "arguments": {}},
                    ],
                }
            )
        return "ok"

    monkeypatch.setattr(lab3_agent.LLMClient, "chat", fake_chat)

    result = await lab3_agent.run_agent(
        dataset_name="customers_reviews.csv",
        question="Сделай отчёт",
        column_overrides={},
        max_tool_calls=2,
        use_critic=False,
        analysis_mode="balanced",
    )
    assert len(result["planner_output"]["tool_calls"]) <= 2


@pytest.mark.asyncio
async def test_critic_review_parse_failed_does_not_break_request(lab3_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_dataset(lab3_paths / "customers_reviews.csv")
    state = {"calls": 0}

    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001,ARG001
        state["calls"] += 1
        if purpose == "planner":
            return json.dumps({"plan": "planner plan", "tool_calls": [{"tool": "get_dataset_schema", "arguments": {}}]})
        if purpose == "critic":
            return "not a json"
        return "Финальный ответ"

    monkeypatch.setattr(lab3_agent.LLMClient, "chat", fake_chat)

    result = await lab3_agent.run_agent(
        dataset_name="customers_reviews.csv",
        question="Сделай обзор",
        column_overrides={},
        max_tool_calls=4,
        use_critic=True,
        analysis_mode="balanced",
    )
    assert result["status"] == "success"
    assert result["critic_review"]["passed"] is None


def test_lab3_status_endpoint(lab3_paths: Path) -> None:
    _write_dataset(lab3_paths / "customers_reviews.csv")
    client = TestClient(app)
    response = client.get("/api/lab3/status")
    assert response.status_code == 200
    assert response.json()["default_mode"] == "code_interpreter"


def test_lab3_profile_endpoint(lab3_paths: Path) -> None:
    _write_dataset(lab3_paths / "customers_reviews.csv")
    client = TestClient(app)
    response = client.get("/api/lab3/profile?dataset_name=customers_reviews.csv")
    assert response.status_code == 200


def test_lab3_tools_endpoint(lab3_paths: Path) -> None:
    _write_dataset(lab3_paths / "customers_reviews.csv")
    client = TestClient(app)
    response = client.get("/api/lab3/tools")
    assert response.status_code == 200


def test_lab3_ask_code_interpreter_mode_mocked(lab3_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_dataset(lab3_paths / "customers_reviews.csv")

    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001,ARG001
        if purpose == "code_interpreter":
            return '{"action":"final_answer","answer":"Готово"}'
        return "ok"

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
            "analysis_mode": "code_interpreter",
        },
    )
    assert response.status_code == 200
    assert response.json()["analysis_mode"] == "code_interpreter"


def test_lab3_request_no_max_code_steps_required(lab3_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_dataset(lab3_paths / "customers_reviews.csv")

    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001,ARG001
        if purpose == "code_interpreter":
            return '{"action":"final_answer","answer":"Готово"}'
        return "ok"

    monkeypatch.setattr(lab3_agent.LLMClient, "chat", fake_chat)
    client = TestClient(app)
    response = client.post(
        "/api/lab3/ask",
        json={
            "dataset_name": "customers_reviews.csv",
            "question": "Сделай обзор",
            "column_overrides": {},
            "analysis_mode": "code_interpreter",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@pytest.mark.asyncio
async def test_lab3_openrouter_does_not_use_ollama_model_ids(lab3_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_dataset(lab3_paths / "customers_reviews.csv")
    models: list[str | None] = []

    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001,ARG001
        models.append(model)
        if purpose == "code_interpreter":
            return '{"action":"final_answer","answer":"ok"}'
        return "ok"

    monkeypatch.setattr(lab3_agent.LLMClient, "chat", fake_chat)
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_model", "openai/gpt-oss-120b:free")

    await lab3_agent.run_agent(
        dataset_name="customers_reviews.csv",
        question="Сделай обзор",
        column_overrides={},
        max_tool_calls=4,
        use_critic=False,
        analysis_mode="code_interpreter",
    )

    assert models
    assert all(model == "openai/gpt-oss-120b:free" for model in models if model is not None)


def test_upload_rejects_unsupported_extension(lab3_paths: Path) -> None:
    client = TestClient(app)
    response = client.post("/api/lab3/upload-dataset", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 400


def test_upload_secure_filename_no_traversal(lab3_paths: Path) -> None:
    client = TestClient(app)
    response = client.post("/api/lab3/upload-dataset", files={"file": ("../../evil file.csv", b"a,b\n1,2\n", "text/csv")})
    assert response.status_code == 200
    dataset_name = response.json()["dataset"]["name"]
    assert ".." not in dataset_name
    assert "uploads/" in dataset_name


def test_lab3_debug_openrouter_ping_mocked(lab3_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.routers import lab3 as lab3_router

    async def fake_ping() -> dict:
        return {"status": "success", "provider": "openrouter", "model": "openai/gpt-oss-120b:free", "elapsed_seconds": 0.1}

    monkeypatch.setattr(lab3_router, "debug_openrouter_ping", fake_ping)
    client = TestClient(app)
    response = client.get("/api/lab3/debug/openrouter-ping")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
