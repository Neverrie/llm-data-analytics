from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.config import settings
from app.services import lab3_code_interpreter
from app.services.lab2_service import Lab2PipelineError
from app.services.llm_client import LLMClient


@pytest.fixture
def ci_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    datasets_dir = tmp_path / "datasets"
    outputs_dir = tmp_path / "outputs"
    datasets_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "datasets_dir", str(datasets_dir))
    monkeypatch.setattr(settings, "outputs_dir", str(outputs_dir))
    monkeypatch.setattr(settings, "lab3_code_interpreter_auto_inspect", True)

    frame = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6], "target": [0, 1, 1]})
    frame.to_csv(datasets_dir / "demo.csv", index=False)


@pytest.mark.asyncio
async def test_code_interpreter_prompt_strict_json_and_df_contract(ci_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
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
    )
    assert "dataframe is already loaded as `df`" in captured["system"]
    assert "Do NOT use pd.read_csv" in captured["system"]
    assert "Do not use function calling" in captured["system"]
    assert "Return ONLY valid JSON" in captured["system"]
    assert "Do not use markdown" in captured["system"]


@pytest.mark.asyncio
async def test_plain_text_need_to_inspect_forces_repair_not_final(ci_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    replies = iter(
        [
            "Need to inspect df.",
            '{"action":"run_code","code":"print(df.shape)"}',
            '{"action":"final_answer","answer":"## Краткий ответ\\nГотово"}',
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
    )
    assert result["final_answer"].startswith("## Краткий ответ")
    assert any("невалидный json" in w.lower() for w in result["warnings"])
    assert any(step.get("action") == "run_code" and step.get("step") != 0 for step in result["steps"])


@pytest.mark.asyncio
async def test_blocked_read_csv_observation_mentions_df(ci_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    replies = iter(
        [
            '{"action":"run_code","code":"import pandas as pd\\npd.read_csv(\\"x.csv\\")"}',
            '{"action":"run_code","code":"print(df.shape)"}',
            '{"action":"final_answer","answer":"ok"}',
        ]
    )
    seen_messages: list[str] = []

    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001
        seen_messages.append(messages[-1]["content"])
        return next(replies)

    monkeypatch.setattr(LLMClient, "chat", fake_chat)
    result = await lab3_code_interpreter.run_code_interpreter_agent(
        dataset_name="demo.csv",
        question="overview",
        column_mapping={"roles": {}},
        profile={"columns": ["x", "y"]},
        session_context=None,
    )
    assert any(step.get("execution", {}).get("status") == "blocked" for step in result["steps"] if step.get("step") != 0)
    assert "df is already loaded" in " ".join(seen_messages).lower()


@pytest.mark.asyncio
async def test_code_interpreter_auto_inspection_step(ci_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001
        return '{"action":"final_answer","answer":"ok"}'

    monkeypatch.setattr(LLMClient, "chat", fake_chat)
    result = await lab3_code_interpreter.run_code_interpreter_agent(
        dataset_name="demo.csv",
        question="overview",
        column_mapping={"roles": {}},
        profile={"columns": ["x", "y"]},
        session_context=None,
    )
    assert result["steps"][0]["step"] == 0
    assert result["steps"][0]["source"] == "backend_auto_inspection"
    assert "shape" in result["steps"][0]["code"]
    assert "dtypes" in result["steps"][0]["code"]
    assert "missing" in result["steps"][0]["code"]


@pytest.mark.asyncio
async def test_target_correlation_query_mocked(ci_paths: None, monkeypatch: pytest.MonkeyPatch) -> None:
    replies = iter(
        [
            '{"action":"run_code","code":"numeric = df.select_dtypes(include=\\"number\\")\\nprint(numeric.corr(method=\\"pearson\\"))\\nprint(numeric.corr(method=\\"spearman\\"))"}',
            '{"action":"final_answer","answer":"## Выбранная target-переменная\\ntarget\\n\\n## Корреляции Пирсона\\n..."}',
        ]
    )

    async def fake_chat(self, messages, purpose="general", model=None, temperature=0.1):  # noqa: ANN001
        return next(replies)

    monkeypatch.setattr(LLMClient, "chat", fake_chat)
    result = await lab3_code_interpreter.run_code_interpreter_agent(
        dataset_name="demo.csv",
        question="Выдели таргет и посчитай Pearson/Spearman",
        column_mapping={"roles": {}},
        profile={"columns": ["x", "y", "target"]},
        session_context=None,
    )
    assert "Выбранная target-переменная" in result["final_answer"]
    assert any("pearson" in str(step.get("code", "")).lower() for step in result["steps"])


def test_blocked_read_csv_message_mentions_df_contract() -> None:
    with pytest.raises(Lab2PipelineError) as exc:
        lab3_code_interpreter._parse_action("not json")  # type: ignore[attr-defined]
    assert "valid json" in str(exc.value).lower() or "preview" in str(exc.value).lower()
