from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.config import settings
from app.services import lab3_code_interpreter
from app.services.llm_client import LLMClient


@pytest.fixture
def ci_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    datasets_dir = tmp_path / "datasets"
    outputs_dir = tmp_path / "outputs"
    datasets_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "datasets_dir", str(datasets_dir))
    monkeypatch.setattr(settings, "outputs_dir", str(outputs_dir))
    monkeypatch.setattr(settings, "lab3_code_interpreter_auto_inspect", False)
    frame = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6], "score": [2, 4, 5]})
    frame.to_csv(datasets_dir / "demo.csv", index=False)


def test_parse_tag_python() -> None:
    parsed = lab3_code_interpreter.parse_code_interpreter_message("<PYTHON>\nprint(df.shape)\n</PYTHON>")
    assert parsed["action"] == "run_code"
    assert "print(df.shape)" in parsed["code"]
    assert parsed["parse_mode"] == "tag_python"


def test_parse_tag_final() -> None:
    parsed = lab3_code_interpreter.parse_code_interpreter_message("<FINAL>\n## Ответ\nok\n</FINAL>")
    assert parsed["action"] == "final_answer"
    assert "## Ответ" in parsed["answer"]
    assert parsed["parse_mode"] == "tag_final"


def test_parse_python_codeblock() -> None:
    parsed = lab3_code_interpreter.parse_code_interpreter_message("```python\nprint(df.shape)\n```")
    assert parsed["action"] == "run_code"
    assert parsed["parse_mode"] == "code_block"


@pytest.mark.asyncio
async def test_need_inspect_df_before_execution_generates_default_inspection_code(ci_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    replies = iter(["Need to inspect df.", "<FINAL>\nok\n</FINAL>"])

    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001
        return next(replies)

    monkeypatch.setattr(LLMClient, "chat", fake_chat)
    result = await lab3_code_interpreter.run_code_interpreter_agent(
        dataset_name="demo.csv",
        question="overview",
        column_mapping={"roles": {}},
        profile={"columns": ["x", "y", "score"]},
        session_context=None,
    )
    assert result["steps"][0]["action"] == "run_code"
    assert "df.shape" in result["steps"][0]["code"]
    assert result["steps"][0]["parse_mode"] == "plain_text_need_inspect_fallback"


@pytest.mark.asyncio
async def test_plain_text_after_success_execution_final_fallback(ci_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    replies = iter(["<PYTHON>\nprint(df.shape)\n</PYTHON>", "Готово: данные проверены."])

    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001
        return next(replies)

    monkeypatch.setattr(LLMClient, "chat", fake_chat)
    result = await lab3_code_interpreter.run_code_interpreter_agent(
        dataset_name="demo.csv",
        question="overview",
        column_mapping={"roles": {}},
        profile={"columns": ["x", "y", "score"]},
        session_context=None,
    )
    assert "Готово" in result["final_answer"]
    assert any(step.get("action") == "final_answer_fallback" for step in result["steps"])


@pytest.mark.asyncio
async def test_code_interpreter_loop_tag_protocol_mocked(ci_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    replies = iter(["<PYTHON>\nprint(df.shape)\n</PYTHON>", "<FINAL>\n## Краткий ответ\nOK\n</FINAL>"])

    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001
        return next(replies)

    monkeypatch.setattr(LLMClient, "chat", fake_chat)
    result = await lab3_code_interpreter.run_code_interpreter_agent(
        dataset_name="demo.csv",
        question="overview",
        column_mapping={"roles": {}},
        profile={"columns": ["x", "y", "score"]},
        session_context=None,
    )
    assert result["successful_executions_count"] == 1
    assert result["final_answer"].startswith("## Краткий ответ")


@pytest.mark.asyncio
async def test_no_json_repair_warning_in_user_warnings(ci_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001
        return "<FINAL>\nok\n</FINAL>"

    monkeypatch.setattr(LLMClient, "chat", fake_chat)
    result = await lab3_code_interpreter.run_code_interpreter_agent(
        dataset_name="demo.csv",
        question="overview",
        column_mapping={"roles": {}},
        profile={"columns": ["x", "y", "score"]},
        session_context=None,
    )
    all_warnings = " ".join(result.get("warnings", [])).lower()
    assert "json" not in all_warnings

