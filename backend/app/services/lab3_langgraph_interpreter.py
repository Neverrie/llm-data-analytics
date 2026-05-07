from __future__ import annotations

import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.config import get_lab3_model, settings
from app.services.code_sandbox import execute_python_code
from app.services.lab2_service import Lab2PipelineError
from app.services.langchain_llm import get_langchain_chat_model

logger = logging.getLogger(__name__)


class GraphState(TypedDict, total=False):
    dataset_name: str
    question: str
    profile: dict[str, Any]
    column_mapping: dict[str, Any]
    messages: list[dict[str, str]]
    code_steps: list[dict[str, Any]]
    generated_files: list[dict[str, Any]]
    final_answer: str | None
    warnings: list[str]
    debug_warnings: list[str]
    llm_calls_count: int
    started_at: float
    status: str
    run_id: str
    iteration: int
    successful_executions_count: int
    llm_raw_outputs: list[dict[str, Any]]
    last_action: Literal["run_code", "final_answer", "parse_failed"] | None
    last_code: str | None
    correction_attempts: int
    parse_mode: str | None
    chat_model: Any


def _system_prompt() -> str:
    return (
        "Всегда отвечай пользователю на русском языке. Исключение: имена колонок, названия файлов, код, stdout/stderr и технические идентификаторы.\n"
        "FINAL answer formatting rules (mandatory):\n"
        "- Use clean Markdown with short sections and bullet points.\n"
        "- Do NOT include technical/debug blocks, trace/result/report file names.\n"
        "- Do NOT write 'saved to output_dir' as the main result.\n"
        "- If charts were created, describe insights briefly; files will be attached as artifacts.\n\n"
        "DataFrame df уже загружен. Используй df.\n"
        "Если нужно явно читать файл, используй только /input/dataset.csv.\n"
        "Сохраняй файлы только в output_dir или /work.\n"
        "Не выдумывай имена созданных файлов. Упоминай только files, которые backend вернул после выполнения.\n\n"
        "Ты работаешь как Code Interpreter для анализа pandas DataFrame.\n\n"
        "Backend уже загрузил датасет в переменную df.\n"
        "Также доступны:\n- output_dir\n- dataset_name\n- column_mapping\n- profile\n\n"
        "Ты должен отвечать только одним из двух блоков:\n\n"
        "<PYTHON>\n# Python-код анализа\n</PYTHON>\n\n"
        "или\n\n"
        "<FINAL>\nMarkdown-ответ на русском\n</FINAL>\n\n"
        "Правила:\n"
        "- Не используй JSON.\n"
        "- Не используй tool_calls/function calling.\n"
        "- Не пиши текст вне тегов.\n"
        "- Датасет уже доступен как df; при явном чтении используй /input/dataset.csv.\n"
        "- Сохраняй результаты только в output_dir (/work внутри sandbox).\n"
        "- Сеть недоступна; не обращайся к внешним API.\n"
        "- Не устанавливай пакеты во время выполнения.\n"
        "- Можно использовать pandas/numpy/matplotlib.\n"
        "- Для графиков сохраняй в output_dir.\n"
        "- Если пользователь просит анализ данных, вычисления, график, кластеризацию, статистику, строки датасета или преобразование данных, твой первый ответ обязан быть <PYTHON>...</PYTHON>.\n"
        "- Не возвращай markdown-объяснение до выполнения кода.\n"
        "- Не утверждай, что файл создан, если код ещё не выполнялся.\n"
        "- Если нужен анализ — напиши <PYTHON>.\n"
        "- После результата кода напиши следующий <PYTHON> или <FINAL>.\n"
        "- После получения <EXECUTION_RESULT> можешь вернуть <FINAL>...</FINAL>.\n"
        "- Финальный ответ на русском Markdown.\n"
        "- Не выдумывай факты вне результатов выполнения кода.\n\n"
        "Пример:\n<PYTHON>\nprint('shape:', df.shape)\nprint(df.dtypes)\nprint(df.isna().sum().sort_values(ascending=False).head(10))\n</PYTHON>"
    )


def parse_langgraph_response(text: str) -> dict[str, Any]:
    source = (text or "").strip()
    if not source:
        return {"action": "parse_failed", "parse_mode": "none"}

    py_match = re.search(r"<PYTHON>\s*(.*?)\s*</PYTHON>", source, flags=re.IGNORECASE | re.DOTALL)
    if py_match and py_match.group(1).strip():
        return {"action": "run_code", "code": py_match.group(1).strip(), "parse_mode": "tag_python"}

    final_match = re.search(r"<FINAL>\s*(.*?)\s*</FINAL>", source, flags=re.IGNORECASE | re.DOTALL)
    if final_match and final_match.group(1).strip():
        return {"action": "final_answer", "answer": final_match.group(1).strip(), "parse_mode": "tag_final"}

    block = re.search(r"```(?:python|py)\s*(.*?)\s*```", source, flags=re.IGNORECASE | re.DOTALL)
    if block and block.group(1).strip():
        return {"action": "run_code", "code": block.group(1).strip(), "parse_mode": "python_codeblock"}

    try:
        parsed = json.loads(source)
        if isinstance(parsed, dict):
            action = str(parsed.get("action", "")).strip()
            if action == "run_code" and isinstance(parsed.get("code"), str):
                return {"action": "run_code", "code": parsed.get("code", "").strip(), "parse_mode": "json_action"}
            if action == "final_answer":
                content = parsed.get("content") if isinstance(parsed.get("content"), str) else parsed.get("answer")
                if isinstance(content, str) and content.strip():
                    return {"action": "final_answer", "answer": content.strip(), "parse_mode": "json_action"}
    except Exception:
        pass

    if source:
        return {"action": "final_answer", "answer": source, "parse_mode": "plain_text_final"}
    return {"action": "parse_failed", "parse_mode": "none"}


def _build_final_fallback_from_steps(steps: list[dict[str, Any]]) -> str:
    if not steps:
        return "Модель не сгенерировала исполняемый Python-код для анализа."
    last = steps[-1] if isinstance(steps[-1], dict) else {}
    execution = last.get("execution") if isinstance(last.get("execution"), dict) else {}
    status = str(execution.get("status") or "unknown")
    stdout = str(execution.get("stdout") or "").strip()
    stderr = str(execution.get("stderr") or "").strip()
    files = execution.get("files") if isinstance(execution.get("files"), list) else []
    file_names = [str(item.get("name") or "") for item in files if isinstance(item, dict) and str(item.get("name") or "").strip()]
    parts = [f"## Результат выполнения\n- Статус: `{status}`"]
    if file_names:
        parts.append("## Артефакты\n" + "\n".join(f"- `{name}`" for name in file_names[:20]))
    if stdout:
        parts.append(f"## stdout\n```\n{stdout[:2000]}\n```")
    if stderr:
        parts.append(f"## stderr\n```\n{stderr[:2000]}\n```")
    return "\n\n".join(parts)


def _save_outputs(payload: dict[str, Any], final_answer: str) -> dict[str, str]:
    out_dir = Path(settings.outputs_dir) / "lab3"
    out_dir.mkdir(parents=True, exist_ok=True)
    result_json = out_dir / "lab3_result.json"
    trace_json = out_dir / "agent_trace.json"
    report_md = out_dir / "lab3_report.md"
    result_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    trace_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(f"# Lab 3 Code Interpreter Report\n\n{final_answer}\n", encoding="utf-8")
    return {
        "agent_trace": str(trace_json),
        "lab3_result_json": str(result_json),
        "lab3_report_md": str(report_md),
        "code_interpreter_trace": str(trace_json),
    }


def _build_graph():
    workflow = StateGraph(GraphState)

    def prepare_context(state: GraphState) -> GraphState:
        chat_model = get_langchain_chat_model(temperature=0)
        return {
            **state,
            "run_id": uuid.uuid4().hex,
            "started_at": time.perf_counter(),
            "status": "running",
            "messages": [
                {"role": "system", "content": _system_prompt()},
                {
                    "role": "user",
                    "content": (
                        f"Question: {state['question']}\n"
                        f"Dataset profile: {json.dumps(state['profile'], ensure_ascii=False)}\n"
                        f"Column mapping: {json.dumps(state['column_mapping'], ensure_ascii=False)}"
                    ),
                },
            ],
            "code_steps": [],
            "generated_files": [],
            "warnings": [],
            "debug_warnings": [],
            "llm_calls_count": 0,
            "llm_raw_outputs": [],
            "iteration": 0,
            "successful_executions_count": 0,
            "correction_attempts": 0,
            "final_answer": None,
            "last_action": None,
            "last_code": None,
            "parse_mode": None,
            "chat_model": chat_model,
        }

    async def llm_step(state: GraphState) -> GraphState:
        model = state["chat_model"]
        msg_objs = []
        for m in state["messages"]:
            if m["role"] == "system":
                msg_objs.append(SystemMessage(content=m["content"]))
            else:
                msg_objs.append(HumanMessage(content=m["content"]))
        llm_calls_inc = 1
        response = await model.ainvoke(msg_objs)
        text = str(getattr(response, "content", "") or "").strip()
        if not text:
            retry_msgs = list(msg_objs)
            retry_msgs.append(HumanMessage(content="Return one block only: <PYTHON>...</PYTHON> or <FINAL>...</FINAL>."))
            retry_resp = await model.ainvoke(retry_msgs)
            text = str(getattr(retry_resp, "content", "") or "").strip()
            llm_calls_inc += 1
        raws = list(state["llm_raw_outputs"])
        raws.append({"iteration": state["iteration"] + 1, "raw": text})
        return {
            **state,
            "llm_calls_count": state["llm_calls_count"] + llm_calls_inc,
            "llm_raw_outputs": raws,
            "iteration": state["iteration"] + 1,
        }

    def parse_response(state: GraphState) -> GraphState:
        raw = state["llm_raw_outputs"][-1]["raw"] if state["llm_raw_outputs"] else ""
        parsed = parse_langgraph_response(raw)
        action = parsed["action"]
        parse_mode = parsed.get("parse_mode")
        messages = list(state["messages"])
        debug_warnings = list(state["debug_warnings"])
        last_code = None
        final_answer = state.get("final_answer")
        successful = state["successful_executions_count"]
        correction_attempts = int(state.get("correction_attempts", 0))
        raw_preview = raw[:280].replace("\n", "\\n")

        if action == "run_code":
            last_code = str(parsed["code"]).strip()
        elif action == "final_answer":
            candidate = str(parsed["answer"]).strip()
            if successful == 0:
                debug_warnings.append(
                    f"LLM returned non-executable response in code interpreter mode. parse_mode={parse_mode}; raw_preview={raw_preview}"
                )
                if correction_attempts < 2:
                    messages.append(
                        {
                            "role": "user",
                            "content": "Ты нарушил формат. Верни только исполняемый Python-код в формате <PYTHON>...</PYTHON>. Не объясняй результат до выполнения кода.",
                        }
                    )
                    correction_attempts += 1
                    action = "parse_failed"
                else:
                    final_answer = "Модель не сгенерировала исполняемый Python-код для анализа."
                    action = "final_answer"
                    parse_mode = "contract_violation_final"
            else:
                final_answer = candidate
        else:
            if successful > 0:
                final_answer = raw.strip()
                action = "final_answer"
                parse_mode = "plain_text_final_fallback"
            elif correction_attempts < 2:
                debug_warnings.append(
                    f"LLM returned non-executable response in code interpreter mode. parse_mode={parse_mode}; raw_preview={raw_preview}"
                )
                messages.append(
                    {
                        "role": "user",
                        "content": "Ты нарушил формат. Верни только исполняемый Python-код в формате <PYTHON>...</PYTHON>. Не объясняй результат до выполнения кода.",
                    }
                )
                correction_attempts += 1
            else:
                final_answer = "Модель не сгенерировала исполняемый Python-код для анализа."
                action = "final_answer"
                parse_mode = "contract_violation_final"

        return {
            **state,
            "messages": messages,
            "debug_warnings": debug_warnings,
            "last_action": action,
            "last_code": last_code,
            "final_answer": final_answer,
            "parse_mode": parse_mode,
            "correction_attempts": correction_attempts,
        }

    def execute_code(state: GraphState) -> GraphState:
        code = state.get("last_code") or ""
        if not code:
            return state
        source = "llm"
        execution = execute_python_code(
            code=code,
            dataset_name=state["dataset_name"],
            run_id=state["run_id"],
            column_mapping=state["column_mapping"],
            profile=state["profile"],
        )
        steps = list(state["code_steps"])
        step_num = len(steps) + 1
        steps.append(
            {
                "step": step_num,
                "source": source,
                "action": "run_code",
                "code": code,
                "parse_mode": state.get("parse_mode"),
                "execution": execution,
            }
        )
        files_map = {f["path"]: f for f in state["generated_files"]}
        for f in execution.get("files", []):
            files_map[f["path"]] = f
        messages = list(state["messages"])
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
        successful = state["successful_executions_count"] + (1 if execution.get("status") == "success" else 0)
        if execution.get("status") == "blocked":
            messages.append({"role": "user", "content": "df is already loaded; do not read files."})
        return {
            **state,
            "code_steps": steps,
            "generated_files": list(files_map.values()),
            "messages": messages,
            "successful_executions_count": successful,
        }

    def should_continue(state: GraphState) -> str:
        if state.get("final_answer"):
            return "finalize"
        elapsed = time.perf_counter() - state["started_at"]
        if elapsed > int(getattr(settings, "lab3_code_interpreter_max_total_seconds", 180)):
            warnings = list(state["warnings"])
            warnings.append("Агент достиг общего таймаута. Показан частичный результат.")
            state["warnings"] = warnings
            state["final_answer"] = "Анализ остановлен по таймауту. Показан частичный результат."
            return "finalize"
        if state["iteration"] >= int(getattr(settings, "lab3_code_interpreter_hard_max_steps", 12)):
            warnings = list(state["warnings"])
            warnings.append("Агент достиг внутреннего лимита защитных шагов. Показан частичный результат.")
            state["warnings"] = warnings
            state["final_answer"] = "Анализ остановлен по внутреннему лимиту шагов. Показан частичный результат."
            return "finalize"
        if state.get("last_action") == "run_code":
            return "execute_code"
        return "llm_step"

    def finalize(state: GraphState) -> GraphState:
        return {**state, "status": "success"}

    workflow.add_node("prepare_context", prepare_context)
    workflow.add_node("llm_step", llm_step)
    workflow.add_node("parse_response", parse_response)
    workflow.add_node("execute_code", execute_code)
    workflow.add_node("finalize", finalize)

    workflow.set_entry_point("prepare_context")
    workflow.add_edge("prepare_context", "llm_step")
    workflow.add_edge("llm_step", "parse_response")
    workflow.add_conditional_edges("parse_response", should_continue, {"execute_code": "execute_code", "llm_step": "llm_step", "finalize": "finalize"})
    workflow.add_edge("execute_code", "llm_step")
    workflow.add_edge("finalize", END)
    return workflow.compile()


async def run_langgraph_code_interpreter(
    dataset_name: str,
    question: str,
    column_mapping: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    logger.info("LAB3_LANGGRAPH_START dataset=%s question_len=%s", dataset_name, len(question or ""))
    app = _build_graph()
    started = time.perf_counter()
    init_state: GraphState = {
        "dataset_name": dataset_name,
        "question": question,
        "profile": profile,
        "column_mapping": column_mapping,
    }
    hard_max_steps = int(getattr(settings, "lab3_code_interpreter_hard_max_steps", 12))
    recursion_limit = max(64, hard_max_steps * 8)
    final_state = await app.ainvoke(init_state, config={"recursion_limit": recursion_limit})
    steps = final_state.get("code_steps", [])
    successful_executions_count = int(final_state.get("successful_executions_count", 0))
    steps_count = len(steps) if isinstance(steps, list) else 0
    final_answer = (final_state.get("final_answer") or "").strip()
    status = "success"
    if steps_count == 0:
        status = "failed_contract"
        final_answer = "Модель не сгенерировала исполняемый Python-код для анализа."
    elif not final_answer:
        final_answer = "Код выполнен, но модель не сформировала текстовый вывод. Ниже показаны результаты выполнения."
    warnings = list(final_state.get("warnings", []))
    debug_warnings = list(final_state.get("debug_warnings", []))
    if steps_count == 0:
        warnings.append("LLM returned non-executable response in code interpreter mode")
        parse_mode = str(final_state.get("parse_mode") or "none")
        raw_messages = final_state.get("llm_raw_outputs", [])
        raw_preview = ""
        if isinstance(raw_messages, list) and raw_messages:
            last_raw = raw_messages[-1] if isinstance(raw_messages[-1], dict) else {}
            raw_preview = str(last_raw.get("raw") or "")[:280].replace("\n", "\\n")
        debug_warnings.append(f"parse_mode={parse_mode}; raw_output_preview={raw_preview}")
    payload = {
        "status": status,
        "mode": "code_interpreter",
        "provider": "openrouter",
        "model": get_lab3_model(),
        "run_id": final_state.get("run_id"),
        "steps": steps,
        "final_answer": final_answer,
        "files": final_state.get("generated_files", []),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "llm_calls_count": int(final_state.get("llm_calls_count", 0)),
        "successful_executions_count": successful_executions_count,
        "warnings": warnings,
        "debug_warnings": debug_warnings,
        "raw_messages": final_state.get("llm_raw_outputs", []),
    }
    payload["output_files"] = _save_outputs(payload, final_answer)
    logger.info(
        "LAB3_LANGGRAPH_DONE elapsed=%.3f llm_calls=%s code_steps=%s",
        payload["elapsed_seconds"],
        payload["llm_calls_count"],
        len(payload["steps"]),
    )
    return payload

