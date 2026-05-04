from __future__ import annotations

import json
import logging
import re
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


def _extract_tag_block(text: str, tag: str) -> str | None:
    pattern = rf"<{tag}>\s*(.*?)\s*</{tag}>"
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def _extract_python_fence(text: str) -> str | None:
    match = re.search(r"```(?:python|py)\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def _looks_like_python_code(text: str) -> bool:
    stripped = text.strip()
    if not stripped or len(stripped.splitlines()) > 200:
        return False
    markers = ["print(", "import pandas", "numeric =", "groupby(", "pivot_table(", "corr(", "df[", "df."]
    if "need to inspect" in stripped.lower():
        return False
    return any(marker in stripped for marker in markers)


def _default_inspection_code() -> str:
    return (
        "print(df.shape)\n"
        "print(df.dtypes)\n"
        "print(df.isna().sum().sort_values(ascending=False).head(15))\n"
        "print(df.head(3).to_string())"
    )


def _looks_like_need_inspect_text(text: str) -> bool:
    low = text.lower()
    return any(token in low for token in ["need to inspect df", "inspect df", "need dataframe", "need data"])


def parse_code_interpreter_message(text: str) -> dict[str, Any]:
    source = (text or "").strip()
    if not source:
        return {"action": "parse_failed", "parse_mode": "none"}

    tag_python = _extract_tag_block(source, "PYTHON")
    if tag_python:
        return {"action": "run_code", "code": tag_python, "parse_mode": "tag_python"}

    tag_final = _extract_tag_block(source, "FINAL")
    if tag_final:
        return {"action": "final_answer", "answer": tag_final, "parse_mode": "tag_final"}

    fenced = _extract_python_fence(source)
    if fenced:
        return {"action": "run_code", "code": fenced, "parse_mode": "code_block"}

    if _looks_like_python_code(source):
        return {"action": "run_code", "code": source, "parse_mode": "python_like_text"}

    # Backward compatibility with old JSON protocol
    try:
        parsed_json = json.loads(source)
        if isinstance(parsed_json, dict):
            action = str(parsed_json.get("action", "")).strip()
            if action == "run_code" and isinstance(parsed_json.get("code"), str):
                return {"action": "run_code", "code": parsed_json["code"], "parse_mode": "legacy_json"}
            if action == "final_answer" and isinstance(parsed_json.get("answer"), str):
                return {"action": "final_answer", "answer": parsed_json["answer"], "parse_mode": "legacy_json"}
    except Exception:
        pass

    return {"action": "parse_failed", "parse_mode": "none"}


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


async def run_code_interpreter_agent(
    dataset_name: str,
    question: str,
    column_mapping: dict,
    profile: dict,
    session_context: str | None,
    max_steps: int = 3,
) -> dict[str, Any]:
    started = time.perf_counter()
    logger.info("LAB3_ASK_START dataset=%s question_len=%s", dataset_name, len(question or ""))
    llm = LLMClient()
    run_id = uuid.uuid4().hex
    model = llm.resolve_model()
    max_total_seconds = int(getattr(settings, "lab3_code_interpreter_max_total_seconds", 180))
    hard_max_steps = int(getattr(settings, "lab3_code_interpreter_hard_max_steps", 12))
    _ = max_steps

    system_prompt = (
        "Ты аналитик данных в режиме Code Interpreter.\n"
        "Backend уже загрузил датасет в pandas DataFrame `df`.\n"
        "Также доступны: output_dir, dataset_name, column_mapping, profile.\n"
        "Работай итеративно:\n"
        "1) Если нужны вычисления — верни только блок <PYTHON>...</PYTHON>.\n"
        "2) Backend выполнит код и вернёт stdout/stderr/files.\n"
        "3) Затем верни следующий <PYTHON> или финальный <FINAL>...</FINAL>.\n"
        "Не возвращай JSON.\n"
        "Не используй markdown вне <FINAL>.\n"
        "Не пиши обычный текст вне тегов.\n"
        "Формат кода:\n"
        "<PYTHON>\nprint(df.shape)\nprint(df.dtypes)\n</PYTHON>\n"
        "Формат финального ответа:\n"
        "<FINAL>\n## Краткий ответ\n...\n</FINAL>\n"
        "Правила:\n"
        "- Датасет уже загружен как df.\n"
        "- Не используй pd.read_csv, pd.read_excel, open, os, subprocess, requests, socket.\n"
        "- Не ищи файлы.\n"
        "- Работай с df.\n"
        "- Можно использовать pandas/numpy/matplotlib.\n"
        "- Для графиков сохраняй в output_dir.\n"
        "- Если код упал, исправь его следующим <PYTHON>.\n"
        "- Финальный ответ пиши на русском.\n"
        "- Не выдумывай факты без stdout/stderr."
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
    debug_warnings: list[str] = []
    raw_messages: list[dict[str, Any]] = []
    llm_calls = 0
    successful_exec_count = 0
    all_files: dict[str, dict[str, Any]] = {}
    final_answer = ""
    correction_used = False
    step_index = 1

    if bool(getattr(settings, "lab3_code_interpreter_auto_inspect", True)):
        logger.info("LAB3_AUTO_INSPECT_START run_id=%s", run_id)
        auto_code = (
            "print('shape:', df.shape)\n"
            "print('columns:', list(df.columns))\n"
            "print('dtypes:')\nprint(df.dtypes)\n"
            "print('missing:')\nprint(df.isna().sum().sort_values(ascending=False).head(15))\n"
            "print('sample:')\nprint(df.head(3).to_string())"
        )
        auto_execution = execute_python_code(
            code=auto_code,
            dataset_name=dataset_name,
            run_id=run_id,
            column_mapping=column_mapping,
            profile=profile,
        )
        if auto_execution.get("status") == "success":
            successful_exec_count += 1
        steps.append({"step": 0, "source": "backend_auto_inspection", "action": "run_code", "code": auto_code, "parse_mode": "backend_auto", "execution": auto_execution})
        messages.append({"role": "user", "content": f"<EXECUTION_RESULT>\nstatus: {auto_execution.get('status')}\nstdout:\n{auto_execution.get('stdout','')}\nstderr:\n{auto_execution.get('stderr','')}\nfiles:\n{json.dumps(auto_execution.get('files', []), ensure_ascii=False)}\n</EXECUTION_RESULT>"})
        logger.info("LAB3_AUTO_INSPECT_DONE run_id=%s status=%s", run_id, auto_execution.get("status"))

    while True:
        if step_index > hard_max_steps:
            warnings.append("Агент достиг внутреннего лимита защитных шагов. Показан частичный результат.")
            break
        if (time.perf_counter() - started) > max_total_seconds:
            warnings.append("Code Interpreter exceeded total timeout.")
            final_answer = "Анализ остановлен по таймауту. Ниже доступны уже выполненные шаги."
            break

        _save_status("openrouter_call", step_index, "Waiting for model response")
        logger.info("LAB3_LLM_CALL_START step=%s", step_index)
        try:
            raw = await llm.chat(messages=messages, purpose="code_interpreter", model=model, temperature=0.1)
            llm_calls += 1
            logger.info("LAB3_LLM_CALL_DONE step=%s content_len=%s", step_index, len(raw or ""))
        except LLMClientError as exc:
            raise Lab2PipelineError(str(exc), status_code=503) from exc

        parsed = parse_code_interpreter_message(raw)
        raw_messages.append({"step": step_index, "raw": raw, "parse_mode": parsed.get("parse_mode"), "action": parsed.get("action")})

        if parsed.get("action") == "run_code":
            code = str(parsed.get("code", "")).strip()
            if not code:
                debug_warnings.append("Empty code block from model.")
                break
            _save_status("sandbox_execution", step_index, "Running python code in sandbox")
            logger.info("LAB3_CODE_EXEC_START step=%s", step_index)
            execution = execute_python_code(
                code=code,
                dataset_name=dataset_name,
                run_id=run_id,
                column_mapping=column_mapping,
                profile=profile,
            )
            logger.info("LAB3_CODE_EXEC_DONE step=%s status=%s", step_index, execution.get("status"))
            if execution.get("status") == "success":
                successful_exec_count += 1
            steps.append({"step": step_index, "source": "llm", "action": "run_code", "code": code, "parse_mode": parsed.get("parse_mode"), "execution": execution})
            for file_item in execution.get("files", []):
                all_files[file_item["path"]] = file_item
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "<EXECUTION_RESULT>\n"
                        f"status: {execution.get('status')}\n"
                        f"stdout:\n{execution.get('stdout', '')}\n"
                        f"stderr:\n{execution.get('stderr', '')}\n"
                        f"files:\n{json.dumps(execution.get('files', []), ensure_ascii=False)}\n"
                        "</EXECUTION_RESULT>"
                    ),
                }
            )
            if execution.get("status") == "blocked":
                messages.append({"role": "user", "content": "Blocked by sandbox. df is already loaded; do not read files."})
            step_index += 1
            continue

        if parsed.get("action") == "final_answer":
            final_answer = str(parsed.get("answer", "")).strip()
            steps.append({"step": step_index, "source": "llm", "action": "final_answer", "parse_mode": parsed.get("parse_mode")})
            break

        if _looks_like_need_inspect_text(raw) and successful_exec_count == 0:
            code = _default_inspection_code()
            execution = execute_python_code(
                code=code,
                dataset_name=dataset_name,
                run_id=run_id,
                column_mapping=column_mapping,
                profile=profile,
            )
            if execution.get("status") == "success":
                successful_exec_count += 1
            steps.append({"step": step_index, "source": "backend_fallback", "action": "run_code", "parse_mode": "plain_text_need_inspect_fallback", "code": code, "execution": execution})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "<EXECUTION_RESULT>\n"
                        f"status: {execution.get('status')}\n"
                        f"stdout:\n{execution.get('stdout', '')}\n"
                        f"stderr:\n{execution.get('stderr', '')}\n"
                        f"files:\n{json.dumps(execution.get('files', []), ensure_ascii=False)}\n"
                        "</EXECUTION_RESULT>"
                    ),
                }
            )
            step_index += 1
            continue

        if successful_exec_count > 0:
            final_answer = raw.strip()
            steps.append({"step": step_index, "source": "fallback", "action": "final_answer_fallback", "parse_mode": "plain_text_final_fallback"})
            break

        if not correction_used:
            correction_used = True
            debug_warnings.append("Model response did not contain <PYTHON> or <FINAL>, correction requested.")
            logger.info("LAB3_TAG_CORRECTION_REQUEST step=%s", step_index)
            messages.append({"role": "user", "content": "Your previous response did not contain <PYTHON> or <FINAL>. Return exactly one of these blocks."})
            continue
        raise Lab2PipelineError("Model did not return <PYTHON> or <FINAL> before any successful execution.", status_code=502)

    if not final_answer:
        final_answer = "Не удалось получить структурированный ответ от модели в формате Code Interpreter."
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
        "successful_executions_count": successful_exec_count,
        "warnings": warnings,
        "debug_warnings": debug_warnings,
        "raw_messages": raw_messages,
    }
    logger.info("LAB3_FINAL_READY elapsed=%.3f llm_calls=%s", result["elapsed_seconds"], llm_calls)
    trace_path = _save_run_trace(run_id, result)
    result_json_path, report_path = _save_lab3_outputs(result, final_answer)
    result["output_files"] = {
        "code_interpreter_trace": str(trace_path),
        "lab3_result_json": result_json_path,
        "lab3_report_md": report_path,
    }
    logger.info("LAB3_ASK_DONE run_id=%s elapsed=%.3f", run_id, result["elapsed_seconds"])
    return result
