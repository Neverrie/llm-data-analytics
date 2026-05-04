from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.code_sandbox import execute_python_code
from app.services.lab2_service import Lab2PipelineError
from app.services.llm_client import LLMClient, LLMClientError


def _parse_action(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            data = json.loads(stripped[start : end + 1])
        else:
            raise Lab2PipelineError(f"Code interpreter action is not valid JSON. Preview: {stripped[:300]}")
    if not isinstance(data, dict):
        raise Lab2PipelineError("Code interpreter action must be JSON object.")
    return data


def _save_run_trace(run_id: str, payload: dict[str, Any]) -> Path:
    run_dir = Path(settings.outputs_dir) / "lab3" / "code_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    trace_path = run_dir / "trace.json"
    trace_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return trace_path


def _save_lab3_outputs(result_payload: dict[str, Any], final_answer: str) -> tuple[str, str]:
    out_dir = Path(settings.outputs_dir) / "lab3"
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / "lab3_result.json"
    result_path.write_text(json.dumps(result_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    report_path = out_dir / "lab3_report.md"
    report_path.write_text(f"# Lab 3 Code Interpreter Report\n\n{final_answer}\n", encoding="utf-8")
    return str(result_path), str(report_path)


async def run_code_interpreter_agent(
    dataset_name: str,
    question: str,
    column_mapping: dict,
    profile: dict,
    session_context: str | None,
    max_steps: int = 5,
) -> dict[str, Any]:
    started = time.perf_counter()
    llm = LLMClient()
    run_id = uuid.uuid4().hex
    model = llm.resolve_model()

    system_prompt = (
        "Ты аналитик данных в режиме code interpreter.\n"
        "Работай через Python-код.\n"
        "У тебя есть DataFrame df и output_dir.\n"
        "Запрещено: os, subprocess, requests, socket, shell-команды, произвольный доступ к файлам.\n"
        "Отвечай только JSON-объектом.\n"
        "Для запуска кода формат:\n"
        '{"action":"run_code","code":"print(df.shape)"}\n'
        "Для финального ответа формат:\n"
        '{"action":"final_answer","answer":"..."}\n'
        "Пиши финальный answer на русском."
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Question: {question}\n"
                f"Dataset profile: {json.dumps(profile, ensure_ascii=False)}\n"
                f"Column mapping: {json.dumps(column_mapping, ensure_ascii=False)}\n"
                f"Session context: {session_context or 'none'}"
            ),
        },
    ]

    steps: list[dict[str, Any]] = []
    warnings: list[str] = []
    llm_calls = 0
    all_files: dict[str, dict[str, Any]] = {}
    final_answer = ""

    for step_index in range(1, max_steps + 1):
        try:
            raw = await llm.chat(messages=messages, purpose="code_interpreter", model=model, temperature=0.1)
            llm_calls += 1
        except LLMClientError as exc:
            raise Lab2PipelineError(str(exc), status_code=503) from exc

        try:
            action = _parse_action(raw)
        except Exception as exc:
            messages.append({"role": "user", "content": f"Invalid JSON action: {exc}. Return valid JSON only."})
            warnings.append("Model returned invalid JSON action; requested retry.")
            continue

        action_name = str(action.get("action", "")).strip()
        if action_name == "run_code":
            code = str(action.get("code", "")).strip()
            if not code:
                messages.append({"role": "user", "content": "Action run_code requires non-empty code."})
                warnings.append("Model returned empty code block.")
                continue

            execution = execute_python_code(code=code, dataset_name=dataset_name, run_id=run_id)
            steps.append({"step": step_index, "action": "run_code", "code": code, "execution": execution})

            for file_item in execution.get("files", []):
                all_files[file_item["path"]] = file_item

            observation = {
                "status": execution.get("status"),
                "stdout": execution.get("stdout", ""),
                "stderr": execution.get("stderr", ""),
                "files": execution.get("files", []),
                "reason": execution.get("reason"),
            }
            messages.append({"role": "user", "content": f"Execution result: {json.dumps(observation, ensure_ascii=False)}"})
            if execution.get("status") == "blocked":
                messages.append({"role": "user", "content": "Code was blocked by sandbox. Rewrite safely."})
            continue

        if action_name == "final_answer":
            final_answer = str(action.get("answer", "")).strip()
            if not final_answer:
                messages.append({"role": "user", "content": "final_answer requires non-empty answer string."})
                warnings.append("Model returned empty final answer; requested retry.")
                continue
            steps.append({"step": step_index, "action": "final_answer"})
            break

        messages.append({"role": "user", "content": "Unknown action. Use run_code or final_answer."})
        warnings.append(f"Unknown action '{action_name}' from model.")

    if not final_answer:
        final_answer = "Частичный ответ: лимит шагов исчерпан, но анализ выполнен не полностью."
        warnings.append("max_code_steps reached before final_answer.")

    result = {
        "mode": "code_interpreter",
        "provider": llm.provider_name(),
        "model": model,
        "run_id": run_id,
        "steps": steps,
        "final_answer": final_answer,
        "files": list(all_files.values()),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "llm_calls_count": llm_calls,
        "warnings": warnings,
    }
    trace_path = _save_run_trace(run_id, result)
    result_json_path, report_path = _save_lab3_outputs(result, final_answer)
    result["output_files"] = {
        "code_interpreter_trace": str(trace_path),
        "lab3_result_json": result_json_path,
        "lab3_report_md": report_path,
    }
    return result
