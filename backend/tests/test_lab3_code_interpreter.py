from __future__ import annotations

from pathlib import Path

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
    assert "Return ONLY a JSON object" in captured["system"]
    assert "Do not use tool_calls" in captured["system"]


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
    assert "Provide overview and observations" in result["final_answer"]
    assert any("fallback" in warning.lower() for warning in result["warnings"])
