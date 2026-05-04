from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.config import settings
from app.services import lab3_langgraph_interpreter as lg


class _Resp:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeModel:
    def __init__(self, responses: list[str]) -> None:
        self._responses = iter(responses)

    async def ainvoke(self, _messages):  # noqa: ANN001
        return _Resp(next(self._responses))


@pytest.fixture
def lg_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    datasets_dir = tmp_path / "datasets"
    outputs_dir = tmp_path / "outputs"
    datasets_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "datasets_dir", str(datasets_dir))
    monkeypatch.setattr(settings, "outputs_dir", str(outputs_dir))
    monkeypatch.setattr(settings, "openrouter_api_key", "test")
    frame = pd.DataFrame({"x": [1, 2, 3], "score": [5, 4, 3]})
    frame.to_csv(datasets_dir / "demo.csv", index=False)


def test_langgraph_parse_python_tag() -> None:
    parsed = lg.parse_langgraph_response("<PYTHON>\nprint(df.shape)\n</PYTHON>")
    assert parsed["action"] == "run_code"


def test_langgraph_parse_final_tag() -> None:
    parsed = lg.parse_langgraph_response("<FINAL>\nГотово\n</FINAL>")
    assert parsed["action"] == "final_answer"


def test_langgraph_parse_python_codeblock() -> None:
    parsed = lg.parse_langgraph_response("```python\nprint(df.shape)\n```")
    assert parsed["action"] == "run_code"
    assert parsed["parse_mode"] == "python_codeblock"


@pytest.mark.asyncio
async def test_langgraph_need_inspect_fallback(lg_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lg, "get_langchain_chat_model", lambda **kwargs: _FakeModel(["Need to inspect df.", "<FINAL>\nok\n</FINAL>"]))
    result = await lg.run_langgraph_code_interpreter(
        dataset_name="demo.csv",
        question="overview",
        column_mapping={"roles": {}},
        profile={"columns": ["x", "score"]},
    )
    assert result["steps"]
    assert result["steps"][0]["parse_mode"] == "fallback_inspection"


@pytest.mark.asyncio
async def test_langgraph_code_interpreter_mock_sequence(lg_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        lg,
        "get_langchain_chat_model",
        lambda **kwargs: _FakeModel(["<PYTHON>\nprint(df.shape)\n</PYTHON>", "<FINAL>\nГотово\n</FINAL>"]),
    )
    result = await lg.run_langgraph_code_interpreter(
        dataset_name="demo.csv",
        question="overview",
        column_mapping={"roles": {}},
        profile={"columns": ["x", "score"]},
    )
    assert result["successful_executions_count"] == 1
    assert result["final_answer"] == "Готово"
    assert result["llm_calls_count"] == 2


@pytest.mark.asyncio
async def test_langgraph_plain_text_after_success_as_final_fallback(lg_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lg, "get_langchain_chat_model", lambda **kwargs: _FakeModel(["<PYTHON>\nprint(df.shape)\n</PYTHON>", "Итог."]))
    result = await lg.run_langgraph_code_interpreter(
        dataset_name="demo.csv",
        question="overview",
        column_mapping={"roles": {}},
        profile={"columns": ["x", "score"]},
    )
    assert result["final_answer"] == "Итог."


@pytest.mark.asyncio
async def test_langgraph_does_not_emit_json_repair_warnings(lg_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lg, "get_langchain_chat_model", lambda **kwargs: _FakeModel(["<FINAL>\nok\n</FINAL>"]))
    result = await lg.run_langgraph_code_interpreter(
        dataset_name="demo.csv",
        question="overview",
        column_mapping={"roles": {}},
        profile={"columns": ["x", "score"]},
    )
    assert not any("json" in w.lower() for w in result.get("warnings", []))
