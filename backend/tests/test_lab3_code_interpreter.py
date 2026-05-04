from __future__ import annotations

from pathlib import Path
import inspect
import time

import pandas as pd
import pytest

from app.config import settings
from app.services import lab3_code_interpreter
from app.services.llm_client import LLMClient, LLMClientError


@pytest.fixture
def ci_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    datasets_dir = tmp_path / "datasets"
    outputs_dir = tmp_path / "outputs"
    datasets_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "datasets_dir", str(datasets_dir))
    monkeypatch.setattr(settings, "outputs_dir", str(outputs_dir))

    frame = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    frame.to_csv(datasets_dir / "demo.csv", index=False)


@pytest.mark.asyncio
async def test_code_interpreter_parses_run_code_action(ci_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    replies = iter([
        '{"action":"run_code","code":"print(df.shape)"}',
        '{"action":"final_answer","answer":"Готово"}',
    ])

    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001
        return next(replies)

    monkeypatch.setattr(LLMClient, "chat", fake_chat)

    result = await lab3_code_interpreter.run_code_interpreter_agent(
        dataset_name="demo.csv",
        question="shape?",
        column_mapping={"roles": {}},
        profile={"columns": ["x", "y"]},
        session_context=None,
        max_steps=4,
    )
    assert result["steps"][0]["action"] == "run_code"
    assert result["steps"][0]["execution"]["status"] == "success"


@pytest.mark.asyncio
async def test_code_interpreter_final_answer(ci_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    replies = iter([
        '{"action":"run_code","code":"print(df.shape)"}',
        '{"action":"final_answer","answer":"Итоговый ответ"}',
    ])

    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001
        return next(replies)

    monkeypatch.setattr(LLMClient, "chat", fake_chat)

    result = await lab3_code_interpreter.run_code_interpreter_agent(
        dataset_name="demo.csv",
        question="overview",
        column_mapping={"roles": {}},
        profile={"columns": ["x", "y"]},
        session_context=None,
        max_steps=4,
    )
    assert result["final_answer"] == "Итоговый ответ"


@pytest.mark.asyncio
async def test_code_interpreter_prompt_forces_json_content(ci_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {"system": ""}

    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001
        captured["system"] = messages[0]["content"]
        return '{"action":"final_answer","answer":"ok"}'

    monkeypatch.setattr(LLMClient, "chat", fake_chat)
    await lab3_code_interpreter.run_code_interpreter_agent(
        dataset_name="demo.csv",
        question="overview",
        column_mapping={"roles": {}},
        profile={"columns": ["x", "y"]},
        session_context=None,
        max_steps=2,
    )
    assert "Return ONLY one JSON object" in captured["system"]
    assert "No tool_calls" in captured["system"]
    assert "already loaded the dataset into pandas DataFrame `df`" in captured["system"]
    assert "Do NOT use pd.read_csv" in captured["system"]
    assert "Do NOT read files yourself" in captured["system"]


@pytest.mark.asyncio
async def test_code_interpreter_handles_missing_text_content_error(ci_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001
        raise LLMClientError("OpenRouter response did not contain usable text. Preview: {}")

    monkeypatch.setattr(LLMClient, "chat", fake_chat)
    with pytest.raises(Exception) as exc:
        await lab3_code_interpreter.run_code_interpreter_agent(
            dataset_name="demo.csv",
            question="overview",
            column_mapping={"roles": {}},
            profile={"columns": ["x", "y"]},
            session_context=None,
            max_steps=2,
        )
    assert "нестандартном формате" in str(exc.value).lower() or "usable text" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_code_interpreter_uses_openrouter_model_not_ollama(ci_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_model", "openai/gpt-oss-120b:free")
    models: list[str | None] = []

    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001
        models.append(model)
        return '{"action":"final_answer","answer":"ok"}'

    monkeypatch.setattr(LLMClient, "chat", fake_chat)
    await lab3_code_interpreter.run_code_interpreter_agent(
        dataset_name="demo.csv",
        question="overview",
        column_mapping={"roles": {}},
        profile={"columns": ["x", "y"]},
        session_context=None,
        max_steps=2,
    )
    assert models and all(model == "openai/gpt-oss-120b:free" for model in models if model)


@pytest.mark.asyncio
async def test_code_interpreter_plain_text_fallback_to_final_answer(ci_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001
        return "We need to output final answer JSON. Provide overview and observations."

    monkeypatch.setattr(LLMClient, "chat", fake_chat)
    result = await lab3_code_interpreter.run_code_interpreter_agent(
        dataset_name="demo.csv",
        question="overview",
        column_mapping={"roles": {}},
        profile={"columns": ["x", "y"]},
        session_context=None,
        max_steps=2,
    )
    assert "не удалось получить структурированный ответ" in result["final_answer"].lower()
    assert any("служебный текст" in warning.lower() for warning in result["warnings"])


@pytest.mark.asyncio
async def test_code_interpreter_meta_text_is_not_returned_as_final_answer(ci_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    replies = iter(
        [
            "We need to output JSON with action final_answer. Provide overview.",
            '{"action":"final_answer","answer":"Краткий обзор: данные загружены, есть пропуски, нужны дополнительные проверки."}',
        ]
    )

    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001
        return next(replies)

    monkeypatch.setattr(LLMClient, "chat", fake_chat)
    result = await lab3_code_interpreter.run_code_interpreter_agent(
        dataset_name="demo.csv",
        question="overview",
        column_mapping={"roles": {}},
        profile={"columns": ["x", "y"]},
        session_context=None,
        max_steps=3,
    )
    assert "we need to output json" not in result["final_answer"].lower()
    assert "краткий обзор" in result["final_answer"].lower()


def test_code_interpreter_default_max_steps_is_3() -> None:
    signature = inspect.signature(lab3_code_interpreter.run_code_interpreter_agent)
    assert signature.parameters["max_steps"].default == 3


@pytest.mark.asyncio
async def test_code_interpreter_total_timeout_returns_partial(ci_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "lab3_code_interpreter_max_total_seconds", 1)

    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001
        time.sleep(1.2)
        return '{"action":"run_code","code":"print(df.shape)"}'

    monkeypatch.setattr(LLMClient, "chat", fake_chat)
    result = await lab3_code_interpreter.run_code_interpreter_agent(
        dataset_name="demo.csv",
        question="overview",
        column_mapping={"roles": {}},
        profile={"columns": ["x", "y"]},
        session_context=None,
        max_steps=3,
    )
    assert result["status"] == "timeout"
    assert any("timeout" in warning.lower() for warning in result["warnings"])


@pytest.mark.asyncio
async def test_code_interpreter_observation_after_blocked_mentions_df(ci_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    replies = iter(
        [
            '{"action":"run_code","code":"import os\\nprint(os.listdir())"}',
            '{"action":"run_code","code":"print(df.shape)"}',
            '{"action":"final_answer","answer":"Готово"}',
        ]
    )
    captured_messages: list[list[dict[str, str]]] = []

    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001
        captured_messages.append(list(messages))
        return next(replies)

    monkeypatch.setattr(LLMClient, "chat", fake_chat)
    result = await lab3_code_interpreter.run_code_interpreter_agent(
        dataset_name="demo.csv",
        question="overview",
        column_mapping={"roles": {}},
        profile={"columns": ["x", "y"]},
        session_context=None,
    )
    assert result["steps"][0]["execution"]["status"] == "blocked"
    assert result["steps"][1]["execution"]["status"] == "success"
    flattened = " ".join(
        m.get("content", "")
        for messages in captured_messages
        for m in messages
        if isinstance(m, dict)
    )
    assert "df is already loaded" in flattened
