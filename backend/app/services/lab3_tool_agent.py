from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.config import get_lab3_model
from app.services.code_sandbox import execute_python_code
from app.services.langchain_llm import get_langchain_chat_model

logger = logging.getLogger(__name__)


def _gemini_retry_delay_seconds(message: str) -> int | None:
    low = message.lower()
    if "quota exceeded" not in low and "resourceexhausted" not in low and "429" not in low:
        return None
    match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", message, flags=re.IGNORECASE)
    if match:
        return max(1, int(float(match.group(1))))
    match = re.search(r"seconds:\s*([0-9]+)", message, flags=re.IGNORECASE)
    if match:
        return max(1, int(match.group(1)))
    return 25


async def _ainvoke_with_quota_retry(model: Any, messages: list[Any], debug_warnings: list[str]) -> Any:
    attempts = 0
    while True:
        attempts += 1
        try:
            return await model.ainvoke(messages)
        except Exception as exc:
            delay = _gemini_retry_delay_seconds(str(exc))
            if delay is None or attempts >= 3:
                raise
            debug_warnings.append(f"gemini_quota_retry_wait={delay}s")
            await asyncio.sleep(min(delay + 1, 60))


def _json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    return value


def _history_to_text(chat_history: list[dict[str, Any]] | None, limit: int = 10) -> str:
    if not chat_history:
        return "РСЃС‚РѕСЂРёСЏ РїСѓСЃС‚Р°."
    rows: list[str] = []
    for item in chat_history[-limit:]:
        role = str(item.get("role") or "user")
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        rows.append(f"{role}: {content[:800]}")
    return "\n".join(rows) if rows else "РСЃС‚РѕСЂРёСЏ РїСѓСЃС‚Р°."


def _tool_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": (
                "Executes Python code in an isolated sandbox with pandas DataFrame df already loaded. "
                "Use it for dataset analysis, calculations, plots, tables, ML, clustering. Save files to output_dir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute in sandbox."},
                },
                "required": ["code"],
                "additionalProperties": False,
            },
        },
    }


async def run_lab3_tool_agent(
    *,
    dataset_name: str,
    question: str,
    column_mapping: dict[str, Any],
    profile: dict[str, Any],
    chat_history: list[dict[str, Any]] | None = None,
    session_id: str | None = None,
    max_tool_calls: int = 6,
    conversation_context: dict[str, Any] | None = None,
    resolved_task: str | None = None,
    followup_intent: dict[str, Any] | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    run_id = run_id or uuid.uuid4().hex
    steps: list[dict[str, Any]] = []
    warnings: list[str] = []
    debug_warnings: list[str] = []
    raw_messages: list[dict[str, Any]] = []
    all_files: dict[str, dict[str, Any]] = {}
    llm_calls_count = 0
    successful_executions_count = 0
    tool_calls_total = 0

    model = get_langchain_chat_model(temperature=0).bind_tools([_tool_schema()])
    system_prompt = (
        "РўС‹ Р°РіРµРЅС‚ Р°РЅР°Р»РёР·Р° РґР°РЅРЅС‹С… СЃ РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРј run_python.\n"
        "Р’СЃРµРіРґР° РѕС‚РІРµС‡Р°Р№ РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ РЅР° СЂСѓСЃСЃРєРѕРј СЏР·С‹РєРµ.\n"
        "РСЃРєР»СЋС‡РµРЅРёРµ: РёРјРµРЅР° РєРѕР»РѕРЅРѕРє, РЅР°Р·РІР°РЅРёСЏ С„Р°Р№Р»РѕРІ, РєРѕРґ, stdout/stderr Рё С‚РµС…РЅРёС‡РµСЃРєРёРµ РёРґРµРЅС‚РёС„РёРєР°С‚РѕСЂС‹.\n\n"
        f"РЈ С‚РµР±СЏ РµСЃС‚СЊ РІС‹Р±СЂР°РЅРЅС‹Р№ РґР°С‚Р°СЃРµС‚: {dataset_name}.\n"
        "Backend СѓР¶Рµ Р·Р°РіСЂСѓР¶Р°РµС‚ РґР°С‚Р°СЃРµС‚ РІ pandas DataFrame df РІРЅСѓС‚СЂРё sandbox.\n"
        "Р’ РєРѕРґРµ РёСЃРїРѕР»СЊР·СѓР№ РїРµСЂРµРјРµРЅРЅСѓСЋ df.\n"
        "Р•СЃР»Рё РЅСѓР¶РЅРѕ СЏРІРЅРѕ РїСЂРѕС‡РёС‚Р°С‚СЊ С„Р°Р№Р», РёСЃРїРѕР»СЊР·СѓР№ С‚РѕР»СЊРєРѕ /input/dataset.csv.\n"
        "РЎРѕС…СЂР°РЅСЏР№ С„Р°Р№Р»С‹ С‚РѕР»СЊРєРѕ РІ output_dir.\n"
        "Р”Р»СЏ РіСЂР°С„РёРєРѕРІ РёСЃРїРѕР»СЊР·СѓР№ matplotlib/seaborn Рё СЃРѕС…СЂР°РЅСЏР№ PNG РІ output_dir.\n"
        "РќРµ СѓСЃС‚Р°РЅР°РІР»РёРІР°Р№ РїР°РєРµС‚С‹ РІРѕ РІСЂРµРјСЏ РІС‹РїРѕР»РЅРµРЅРёСЏ.\n"
        "РЎРµС‚СЊ РЅРµРґРѕСЃС‚СѓРїРЅР°.\n"
        "РќРµ РІС‹РґСѓРјС‹РІР°Р№ СЂРµР·СѓР»СЊС‚Р°С‚С‹ Рё РёРјРµРЅР° С„Р°Р№Р»РѕРІ.\n"
        "РЈРїРѕРјРёРЅР°Р№ С‚РѕР»СЊРєРѕ С„Р°Р№Р»С‹, РєРѕС‚РѕСЂС‹Рµ РІРµСЂРЅСѓР» tool run_python.\n"
        "Р•СЃР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РїСЂРѕСЃРёС‚ Р°РЅР°Р»РёР· РґР°РЅРЅС‹С…, РІС‹С‡РёСЃР»РµРЅРёСЏ, РіСЂР°С„РёРєРё, РєР»Р°СЃС‚РµСЂРёР·Р°С†РёСЋ, СЃС‚Р°С‚РёСЃС‚РёРєСѓ, С‚Р°Р±Р»РёС†С‹, ML РёР»Рё СЃС‚СЂРѕРєРё РґР°С‚Р°СЃРµС‚Р° вЂ” РІС‹Р·РѕРІРё run_python.\n"
        "РџРѕСЃР»Рµ РїРѕР»СѓС‡РµРЅРёСЏ СЂРµР·СѓР»СЊС‚Р°С‚Р° run_python РґР°Р№ С„РёРЅР°Р»СЊРЅС‹Р№ РѕС‚РІРµС‚ РЅР° СЂСѓСЃСЃРєРѕРј Markdown.\n"
        "РќРµ РІС‹РІРѕРґРё Р±РѕР»СЊС€РёРµ markdown-С‚Р°Р±Р»РёС†С‹.\n"
        "РќРµ РІС‹РІРѕРґРё markdown-С‚Р°Р±Р»РёС†С‹ РІРѕРѕР±С‰Рµ.\n"
        "РќРµ РІС‹РІРѕРґРё markdown-РєР°СЂС‚РёРЅРєРё РІРѕРѕР±С‰Рµ.\n"
        "РќРµ РёСЃРїРѕР»СЊР·СѓР№ СЃРёРЅС‚Р°РєСЃРёСЃ ![...](...).\n"
        "РќРµ РІСЃС‚Р°РІР»СЏР№ РёРјРµРЅР° С„Р°Р№Р»РѕРІ РєР°Рє РєР°СЂС‚РёРЅРєРё.\n"
        "РќРµ РїРµСЂРµС‡РёСЃР»СЏР№ РіСЂР°С„РёРєРё РІ С‚Р°Р±Р»РёС†Рµ.\n"
        "Р•СЃР»Рё РґР°РЅРЅС‹Рµ СѓР¶Рµ РµСЃС‚СЊ РІ stdout/files/table artifacts, РґР°Р№ РєСЂР°С‚РєРёРµ РІС‹РІРѕРґС‹.\n"
        "РўР°Р±Р»РёС‡РЅС‹Рµ РґР°РЅРЅС‹Рµ Р±СѓРґСѓС‚ РѕС‚РѕР±СЂР°Р¶РµРЅС‹ РѕС‚РґРµР»СЊРЅС‹РјРё UI-Р±Р»РѕРєР°РјРё.\n"
        "Р¤РёРЅР°Р»СЊРЅС‹Р№ РѕС‚РІРµС‚ РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ С‚РѕР»СЊРєРѕ РєСЂР°С‚РєРёРј С‚РµРєСЃС‚РѕРј: 3-7 bullet points СЃ РІС‹РІРѕРґР°РјРё.\n"
        "Р•СЃР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РїСЂРѕСЃРёС‚ РїРµСЂРІС‹Рµ СЃС‚СЂРѕРєРё РґР°С‚Р°СЃРµС‚Р°, РЅРµ РїРµС‡Р°С‚Р°Р№ РёС… markdown-С‚Р°Р±Р»РёС†РµР№: backend РїРѕРєР°Р¶РµС‚ table block.\n"
        "Р•СЃР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РїСЂРѕСЃРёС‚ РіСЂР°С„РёРєРё, РЅРµ РІСЃС‚Р°РІР»СЏР№ РёС… РІ markdown: backend РїРѕРєР°Р¶РµС‚ chart blocks.\n"
        "Р•СЃР»Рё run_python РІРµСЂРЅСѓР» РѕС€РёР±РєСѓ, РѕР±СЉСЏСЃРЅРё РѕС€РёР±РєСѓ Рё, РµСЃР»Рё РІРѕР·РјРѕР¶РЅРѕ, РёСЃРїСЂР°РІСЊ РєРѕРґ РµС‰С‘ РѕРґРЅРёРј РІС‹Р·РѕРІРѕРј run_python.\n"
        "РќРµ РѕС‚РІРµС‡Р°Р№ С„РёРЅР°Р»СЊРЅРѕ РЅР° Р°РЅР°Р»РёС‚РёС‡РµСЃРєРёР№ Р·Р°РїСЂРѕСЃ РґРѕ РІС‹Р·РѕРІР° run_python.\n"
        "Р”Р»СЏ С‚Р°Р±Р»РёС‡РЅС‹С… СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ СЃРѕС…СЂР°РЅСЏР№ CSV-С„Р°Р№Р» РІ output_dir (РЅР°РїСЂРёРјРµСЂ: head.csv, summary.csv).\n"
        "Р•СЃР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РїСЂРѕСЃРёС‚ РїРµСЂРІС‹Рµ СЃС‚СЂРѕРєРё/head/preview, СЃРѕС…СЂР°РЅСЏР№ df.head(N) РІ output_dir/head.csv.\n"
        "If user asks for several independent charts, create separate figure and separate PNG for each chart.\n"
        "Do not combine independent charts into one canvas/subplots.\n"
        "Use subplots/shared canvas only when user explicitly asks comparison in one panel, or for logically linked comparison views like correlation matrix/pairplot/confusion matrix/dashboard summary.\n"
        "For each separate chart use: plt.figure(...), ..., plt.tight_layout(), plt.savefig(output_dir / '<meaningful_name>.png', dpi=150), plt.close().\n"
        "Use meaningful latin file names like sales_distribution.png, profit_distribution.png, region_counts.png.\n"
        "Do not embed images in markdown final answer. Backend will render PNGs as chart blocks.\n"
        "If followup_intent=new_task, execute the current request as a new standalone task. "
        "Do not continue previous task unless user explicitly asks to continue/retry/refine."
    )
    conversation_context = conversation_context or {}
    followup_intent = followup_intent or {}
    user_prompt = (
        f"Вопрос пользователя:\n{question}\n\n"
        f"Resolved task (главная цель):\n{resolved_task or question}\n\n"
        f"Follow-up intent:\n{json.dumps(followup_intent, ensure_ascii=False)}\n\n"
        f"Контекст текущего чата:\n{json.dumps(conversation_context, ensure_ascii=False)}\n\n"
        f"Профиль датасета:\n{json.dumps(profile, ensure_ascii=False)}\n\n"
        f"Column mapping:\n{json.dumps(column_mapping, ensure_ascii=False)}\n\n"
        f"Краткая история чата:\n{_history_to_text(chat_history)}"
    )
    messages: list[Any] = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    final_answer = ""

    for _ in range(max_tool_calls + 2):
        resp = await _ainvoke_with_quota_retry(model, messages, debug_warnings)
        llm_calls_count += 1
        raw_messages.append(
            {
                "type": "ai",
                "content": str(getattr(resp, "content", "") or ""),
                "tool_calls": getattr(resp, "tool_calls", []) or [],
            }
        )
        messages.append(resp)
        tool_calls = list(getattr(resp, "tool_calls", []) or [])
        if tool_calls:
            for call in tool_calls:
                name = str(call.get("name") or "")
                tool_call_id = str(call.get("id") or "")
                args = call.get("args") if isinstance(call.get("args"), dict) else {}
                if name != "run_python":
                    tool_payload = {"status": "error", "stderr": f"Unknown tool: {name}"}
                    messages.append(ToolMessage(content=json.dumps(tool_payload, ensure_ascii=False), tool_call_id=tool_call_id))
                    continue
                code = str(args.get("code") or "").strip()
                if not code:
                    tool_payload = {"status": "error", "stderr": "Tool run_python called without code."}
                    messages.append(ToolMessage(content=json.dumps(tool_payload, ensure_ascii=False), tool_call_id=tool_call_id))
                    continue

                step_num = len(steps) + 1
                execution = execute_python_code(
                    code=code,
                    dataset_name=dataset_name,
                    run_id=run_id,
                    user_id=user_id,
                    step=step_num,
                    column_mapping=column_mapping,
                    profile=profile,
                )
                tool_calls_total += 1
                if execution.get("status") == "success":
                    successful_executions_count += 1
                for f in (execution.get("files") or []):
                    if isinstance(f, dict):
                        path = str(f.get("path") or "")
                        if path:
                            all_files[path] = f
                steps.append(
                    {
                        "step": step_num,
                        "source": "llm_tool_call",
                        "tool": "run_python",
                        "code": code,
                        "execution": execution,
                    }
                )
                tool_result = {
                    "status": execution.get("status"),
                    "stdout": execution.get("stdout", ""),
                    "stderr": execution.get("stderr", ""),
                    "files": execution.get("files", []),
                    "elapsed_seconds": execution.get("elapsed_seconds"),
                }
                messages.append(
                    ToolMessage(
                        content=json.dumps(_json_safe(tool_result), ensure_ascii=False),
                        tool_call_id=tool_call_id,
                    )
                )
            continue

        content = str(getattr(resp, "content", "") or "").strip()
        if content:
            final_answer = content
            break

    status = "success"
    cancelled_steps = [
        s for s in steps
        if isinstance(s, dict) and isinstance(s.get("execution"), dict) and str(s["execution"].get("status") or "").lower() == "cancelled"
    ]
    if cancelled_steps:
        status = "cancelled"
        final_answer = "Запрос остановлен пользователем."
    elif len(steps) == 0:
        status = "failed_contract"
        final_answer = "РњРѕРґРµР»СЊ РЅРµ РІС‹Р·РІР°Р»Р° run_python РґР»СЏ Р°РЅР°Р»РёР·Р° РґР°РЅРЅС‹С…."
        warnings.append("LLM returned non-executable response in code interpreter mode")
        last = raw_messages[-1] if raw_messages else {}
        preview = str(last.get("content") or "")[:280].replace("\n", "\\n")
        debug_warnings.append(f"raw_output_preview={preview}")
    elif successful_executions_count == 0:
        status = "error"
        last_exec = steps[-1].get("execution", {}) if steps else {}
        stderr = str(last_exec.get("stderr") or "").strip()
        final_answer = f"РљРѕРґ РЅРµ РІС‹РїРѕР»РЅРёР»СЃСЏ. РћС€РёР±РєР° sandbox: {stderr[:1200]}" if stderr else "РљРѕРґ РЅРµ РІС‹РїРѕР»РЅРёР»СЃСЏ."
    elif not final_answer:
        final_answer = "РљРѕРґ РІС‹РїРѕР»РЅРµРЅ, РЅРѕ РјРѕРґРµР»СЊ РЅРµ СЃС„РѕСЂРјРёСЂРѕРІР°Р»Р° С‚РµРєСЃС‚РѕРІС‹Р№ РІС‹РІРѕРґ. РќРёР¶Рµ РїРѕРєР°Р·Р°РЅС‹ СЂРµР·СѓР»СЊС‚Р°С‚С‹ РІС‹РїРѕР»РЅРµРЅРёСЏ."

    return {
        "status": status,
        "mode": "tool_calling_code_interpreter",
        "provider": "openrouter",
        "model": get_lab3_model(),
        "run_id": run_id,
        "steps": steps,
        "final_answer": final_answer,
        "files": list(all_files.values()),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "llm_calls_count": llm_calls_count,
        "successful_executions_count": successful_executions_count,
        "warnings": warnings,
        "debug_warnings": debug_warnings,
        "raw_messages": raw_messages,
        "session_id": session_id,
        "tool_calls_count": tool_calls_total,
    }

