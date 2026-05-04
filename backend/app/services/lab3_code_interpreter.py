from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.code_sandbox import execute_python_code
from app.services.lab2_service import Lab2PipelineError
from app.services.llm_client import LLMClient, LLMClientError

logger = logging.getLogger(__name__)


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


def _as_fallback_final_answer(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    if len(cleaned) > 4000:
        return cleaned[:4000] + "..."
    return cleaned


def _looks_like_meta_json_instruction(text: str) -> bool:
    low = text.lower()
    markers = [
        "we need to output json",
        "output json",
        "action final_answer",
        "provide overview",
        "return valid json",
        "your previous response was not valid json",
        "json with action",
    ]
    return any(marker in low for marker in markers)


def _save_run_trace(run_id: str, payload: dict[str, Any]) -> Path:
    run_dir = Path(settings.outputs_dir) / "lab3" / "code_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    trace_path = run_dir / "trace.json"
    trace_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return trace_path


def _save_status(stage: str, step: int, message: str) -> None:
    path = Path(settings.outputs_dir) / "lab3"
    path.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "running",
        "stage": stage,
        "step": step,
        "message": message,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    (path / "current_status.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_lab3_outputs(result_payload: dict[str, Any], final_answer: str) -> tuple[str, str]:
    out_dir = Path(settings.outputs_dir) / "lab3"
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / "lab3_result.json"
    result_path.write_text(json.dumps(result_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    report_path = out_dir / "lab3_report.md"
    report_path.write_text(f"# Lab 3 Code Interpreter Report\n\n{final_answer}\n", encoding="utf-8")
    return str(result_path), str(report_path)


def _timeout_result(
    *,
    llm: LLMClient,
    model: str,
    run_id: str,
    steps: list[dict[str, Any]],
    all_files: dict[str, dict[str, Any]],
    llm_calls: int,
    warnings: list[str],
    started: float,
) -> dict[str, Any]:
    warnings = warnings + ["Code Interpreter exceeded total timeout."]
    final_answer = "Анализ остановлен по таймауту. Ниже доступны уже выполненные шаги."
    return {
        "status": "timeout",
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
        "raw_previews": [],
    }


async def run_code_interpreter_agent(
    dataset_name: str,
    question: str,
    column_mapping: dict,
    profile: dict,
    session_context: str | None,
    max_steps: int = 3,
) -> dict[str, Any]:
    started = time.perf_counter()
    llm = LLMClient()
    run_id = uuid.uuid4().hex
    model = llm.resolve_model()
    max_total_seconds = int(getattr(settings, "lab3_code_interpreter_max_total_seconds", 180))
    hard_max_steps = int(getattr(settings, "lab3_code_interpreter_hard_max_steps", 12))
    _ = max_steps  # compatibility

    system_prompt = (
        "You are working in Code Interpreter mode for tabular data analysis.\n"
        "IMPORTANT: backend already loaded the dataset into pandas DataFrame `df`.\n"
        "Do NOT read files yourself. Do NOT use pd.read_csv, pd.read_excel, open, os, pathlib, subprocess, requests, socket, or shell commands.\n"
        "Do NOT search for files or directories.\n"
        "Work only with available variables:\n"
        "- df: pandas DataFrame\n"
        "- output_dir: directory for charts/results\n"
        "- dataset_name: dataset name\n"
        "- column_mapping: inferred column roles\n"
        "- profile: dataset profile summary\n"
        "Allowed libraries are already imported by backend: pandas as pd, numpy as np, matplotlib.pyplot as plt, json, math, statistics, re, Counter/defaultdict, datetime.\n"
        "If you need a chart, save it only to output_dir.\n"
        "Return ONLY one JSON object in message content. No markdown. No tool_calls. No function calling. No text before or after JSON.\n"
        "For code execution use:\n"
        "{\"action\":\"run_code\",\"code\":\"print(df.shape)\"}\n"
        "For final answer use:\n"
        "{\"action\":\"final_answer\",\"answer\":\"...\"}\n"
        "Rules:\n"
        "1. First do short df inspection.\n"
        "2. Do not invent facts without code execution.\n"
        "3. If code failed or was blocked, fix code using the error message.\n"
        "4. Do not repeat forbidden operations.\n"
        "5. Final answer must be in Russian and mention what was computed.\n"
        "6. Keep one code step short, preferably <=40 lines.\n"
        "First step for overview should be close to:\n"
        "{\"action\":\"run_code\",\"code\":\"print('shape:', df.shape)\\nprint('dtypes:')\\nprint(df.dtypes)\\nprint('missing:')\\nprint(df.isna().sum().sort_values(ascending=False).head(10))\\nprint('sample:')\\nprint(df.head(3).to_string())\"}\n"
        "If you use os, pd.read_csv, open or try to find files, code will be blocked. Use df directly."
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
    blocked_count = 0
    last_block_reason = ""
    invalid_json_count = 0

    step_index = 1
    while True:
        if step_index > hard_max_steps:
            warnings.append("Достигнут внутренний лимит шагов Code Interpreter. Возвращён частичный результат.")
            break
        elapsed_total = time.perf_counter() - started
        if elapsed_total > max_total_seconds:
            logger.warning("LAB3_TIMEOUT total_elapsed=%.3f max_total=%s", elapsed_total, max_total_seconds)
            result = _timeout_result(
                llm=llm,
                model=model,
                run_id=run_id,
                steps=steps,
                all_files=all_files,
                llm_calls=llm_calls,
                warnings=warnings,
                started=started,
            )
            trace_path = _save_run_trace(run_id, result)
            result_json_path, report_path = _save_lab3_outputs(result, result["final_answer"])
            result["output_files"] = {
                "code_interpreter_trace": str(trace_path),
                "lab3_result_json": result_json_path,
                "lab3_report_md": report_path,
            }
            return result

        _save_status("openrouter_call", step_index, "Waiting for model to generate code")
        logger.info(
            "LAB3_LLM_CALL_START step=%s model=%s messages=%s approx_prompt_chars=%s",
            step_index,
            model,
            len(messages),
            sum(len(m.get("content", "")) for m in messages),
        )

        raw: str | None = None
        for repair_attempt in range(0, 3):
            llm_started = time.perf_counter()
            try:
                raw = await llm.chat(messages=messages, purpose="code_interpreter", model=model, temperature=0.1)
                llm_calls += 1
                logger.info(
                    "LAB3_LLM_CALL_DONE step=%s elapsed=%.3f used_model=%s content_len=%s",
                    step_index,
                    time.perf_counter() - llm_started,
                    model,
                    len(raw or ""),
                )
                break
            except LLMClientError as exc:
                msg = str(exc)
                logger.error("LAB3_LLM_CALL_ERROR step=%s elapsed=%.3f error=%s", step_index, time.perf_counter() - llm_started, msg)
                if "did not contain usable text" in msg.lower():
                    raise Lab2PipelineError(
                        f"OpenRouter вернул ответ в нестандартном формате. {msg}",
                        status_code=502,
                    ) from exc
                raise Lab2PipelineError(msg, status_code=503) from exc

        if raw is None:
            raise Lab2PipelineError("Code interpreter failed to receive response from model.", status_code=503)

        action: dict[str, Any] | None = None
        last_parse_error: Exception | None = None
        for repair_attempt in range(0, 3):
            try:
                action = _parse_action(raw)
                break
            except Exception as exc:
                last_parse_error = exc
                if repair_attempt >= 2:
                    break
                messages.append(
                    {
                        "role": "user",
                        "content": "Your previous response was not valid JSON. Return ONLY valid JSON in message content.",
                    }
                )
                warnings.append("Модель вернула невалидный JSON, запрошен повтор.")
                try:
                    raw = await llm.chat(messages=messages, purpose="code_interpreter", model=model, temperature=0.1)
                    llm_calls += 1
                except LLMClientError as llm_exc:
                    raise Lab2PipelineError(str(llm_exc), status_code=503) from llm_exc

        if action is None:
            fallback_answer = _as_fallback_final_answer(raw)
            if fallback_answer:
                if _looks_like_meta_json_instruction(fallback_answer):
                    invalid_json_count += 1
                    warnings.append("Модель вернула служебный текст вместо ответа. Выполнен дополнительный запрос final_answer.")
                    if invalid_json_count >= 3:
                        warnings.append("Code Interpreter: повторяющийся невалидный формат ответа от модели.")
                        break
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Your previous message was meta-instruction text, not a user-facing answer. "
                                "Return ONLY valid JSON with action='final_answer' and a concise Russian answer in 'answer'."
                            ),
                        }
                    )
                    continue
                warnings.append(
                    "Модель вернула обычный текст вместо JSON action. Ответ принят как final_answer (fallback)."
                )
                if last_parse_error is not None:
                    warnings.append(f"JSON parse warning: {last_parse_error}")
                final_answer = fallback_answer
                steps.append({"step": step_index, "action": "final_answer_fallback"})
                break
            raise Lab2PipelineError("Code interpreter action is empty.", status_code=502)

        action_name = str(action.get("action", "")).strip()
        if action_name == "run_code":
            code = str(action.get("code", "")).strip()
            if not code:
                messages.append({"role": "user", "content": "Action run_code requires non-empty code."})
                warnings.append("Model returned empty code block.")
                continue

            _save_status("sandbox_execution", step_index, "Running python code in sandbox")
            logger.info("LAB3_CODE_EXEC_START step=%s code_chars=%s", step_index, len(code))
            exec_started = time.perf_counter()
            execution = execute_python_code(
                code=code,
                dataset_name=dataset_name,
                run_id=run_id,
                column_mapping=column_mapping,
                profile=profile,
            )
            logger.info(
                "LAB3_CODE_EXEC_DONE step=%s status=%s elapsed=%.3f stdout_len=%s stderr_len=%s",
                step_index,
                execution.get("status"),
                time.perf_counter() - exec_started,
                len(execution.get("stdout", "") or ""),
                len(execution.get("stderr", "") or ""),
            )
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
                reason = str(execution.get("reason", "unknown reason"))
                blocked_count += 1
                if reason == last_block_reason:
                    blocked_count += 1
                last_block_reason = reason
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Your code was blocked by sandbox: {reason}. "
                            "Remember: df is already loaded. Do not read files, do not import os, do not use pd.read_csv. "
                            "Write code that operates directly on df."
                        ),
                    }
                )
                if blocked_count >= 2:
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "You repeatedly used forbidden operations. The next response must use df directly. "
                                "Example: {\"action\":\"run_code\",\"code\":\"print(df.shape)\"}"
                            ),
                        }
                    )
                if blocked_count >= 3:
                    warnings.append("Модель не смогла адаптироваться к sandbox-ограничениям. Попробуйте повторить запрос.")
                    break
            elif execution.get("status") == "error":
                stderr = str(execution.get("stderr", ""))
                if "filenotfounderror" in stderr.lower():
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Your code tried to read a file manually. This is not allowed and not needed. "
                                "The dataframe is already available as df. Continue using df directly."
                            ),
                        }
                    )
            step_index += 1
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

        step_index += 1

    if not final_answer:
        final_answer = (
            "Не удалось получить структурированный ответ от модели в формате Code Interpreter. "
            "Попробуйте повторить запрос или уменьшить сложность вопроса."
        )
        warnings.append("Code Interpreter завершился без final_answer.")

    result = {
        "status": "success",
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
        "raw_previews": [],
    }
    logger.info(
        "LAB3_FINAL_READY elapsed=%.3f llm_calls=%s code_steps=%s",
        result["elapsed_seconds"],
        llm_calls,
        len(steps),
    )
    trace_path = _save_run_trace(run_id, result)
    result_json_path, report_path = _save_lab3_outputs(result, final_answer)
    result["output_files"] = {
        "code_interpreter_trace": str(trace_path),
        "lab3_result_json": result_json_path,
        "lab3_report_md": report_path,
    }
    return result
