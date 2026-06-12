import json
import uuid
from typing import Any, Callable

from app.agents.completion import (
    finalize_user_answer,
    is_usable_finalization,
    needs_finalization,
)
from app.agents.models import AgentResult, AgentStep
from app.agents.prompts import (
    build_context_messages,
    build_error_recovery_message,
    build_incomplete_answer_message,
    build_missing_artifacts_message,
    build_system_prompt,
)
from app.agents.requirements import (
    is_analytical_request,
    missing_file_extensions,
    required_file_extensions,
)
from app.agents.tool_executor import execute_tool_call
from app.llm.client import LlmClient, LlmClientError
from app.mcp.server import McpToolServer

MAX_CONSECUTIVE_ERRORS = 3


def _result(
    status: str,
    final_answer: str,
    steps: list[AgentStep],
    files: dict[str, dict[str, Any]],
) -> AgentResult:
    return AgentResult(
        final_answer=final_answer,
        steps=steps,
        files=list(files.values()),
        status=status,
    )


def _emit(
    callback: Callable[[dict[str, Any]], None] | None,
    payload: dict[str, Any],
) -> None:
    if callback:
        callback(payload)


def _remember_files(
    files_by_path: dict[str, dict[str, Any]],
    result_content: dict[str, Any],
) -> None:
    result_files = result_content.get("files") or []
    if not isinstance(result_files, list):
        return
    for item in result_files:
        if not isinstance(item, dict):
            continue
        key = str(item.get("path") or item.get("filename") or "")
        if key:
            files_by_path[key] = item


def _assistant_tool_message(response: Any, step_index: int) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": response.content or "",
        "tool_calls": [
            {
                "id": call.id or f"call-{step_index}",
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments, ensure_ascii=False),
                },
            }
            for call in response.tool_calls
        ],
    }


def _cancelled(
    should_cancel: Callable[[], bool] | None,
    steps: list[AgentStep],
    files: dict[str, dict[str, Any]],
) -> AgentResult | None:
    if should_cancel and should_cancel():
        return _result("cancelled", "Выполнение остановлено пользователем.", steps, files)
    return None


def run_dataset_agent(
    chat_id: str,
    user_message: str,
    dataset_path: str | None = None,
    max_steps: int = 30,
    should_cancel: Callable[[], bool] | None = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
    conversation_context: str | None = None,
    existing_artifacts: list[dict[str, Any]] | None = None,
) -> AgentResult:
    _ = chat_id
    llm = LlmClient()
    server = McpToolServer()
    tools = server.list_tools()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": build_system_prompt(bool(dataset_path))},
        *build_context_messages(conversation_context, existing_artifacts),
        {"role": "user", "content": user_message},
    ]

    steps: list[AgentStep] = []
    files_by_path: dict[str, dict[str, Any]] = {}
    required_extensions = required_file_extensions(user_message)
    analytical_request = is_analytical_request(user_message)
    agent_run_id = f"agent-{uuid.uuid4()}"
    had_tool_call = False
    last_tool_failed = False
    consecutive_errors = 0

    for step_index in range(1, max_steps + 1):
        cancelled = _cancelled(should_cancel, steps, files_by_path)
        if cancelled:
            return cancelled

        try:
            response = llm.chat(messages=messages, tools=tools)
        except LlmClientError as exc:
            return _result("error", str(exc), steps, files_by_path)

        steps.append(
            AgentStep(
                step_index=step_index,
                type="llm",
                content={
                    "content": response.content,
                    "tool_calls": [call.model_dump() for call in response.tool_calls],
                },
            )
        )
        _emit(
            on_event,
            {
                "stage": "llm_step",
                "step": step_index,
                "tool_calls": len(response.tool_calls),
                "message": f"Шаг модели {step_index}",
            },
        )

        if response.tool_calls:
            had_tool_call = True
            messages.append(_assistant_tool_message(response, step_index))
            turn_failed = False

            for call_index, call in enumerate(response.tool_calls):
                cancelled = _cancelled(should_cancel, steps, files_by_path)
                if cancelled:
                    return cancelled

                execution = execute_tool_call(
                    server=server,
                    tool_name=call.name,
                    tool_arguments=call.arguments,
                    call_id=call.id,
                    dataset_path=dataset_path,
                    run_id=agent_run_id,
                    call_index=call_index,
                )
                result = execution.result
                _remember_files(files_by_path, result.content)

                steps.append(
                    AgentStep(
                        step_index=step_index,
                        type="tool",
                        content={
                            "tool_name": call.name,
                            "tool_arguments": execution.arguments,
                            "result": result.model_dump(),
                        },
                    )
                )
                _emit(
                    on_event,
                    {
                        "stage": "tool_result",
                        "step": step_index,
                        "message": f"Инструмент {call.name} завершил работу",
                        "sandbox_status": result.content.get("sandbox_status") or result.status,
                        "elapsed_seconds": result.content.get("elapsed_seconds"),
                        "error": result.error,
                    },
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": json.dumps(result.content, ensure_ascii=False),
                    }
                )
                turn_failed = turn_failed or result.status != "success"

            last_tool_failed = turn_failed
            if turn_failed:
                consecutive_errors += 1
                filenames = sorted(
                    str(item.get("filename"))
                    for item in files_by_path.values()
                    if item.get("filename")
                )
                messages.append(
                    {
                        "role": "user",
                        "content": build_error_recovery_message(
                            consecutive_errors,
                            MAX_CONSECUTIVE_ERRORS,
                            filenames,
                        ),
                    }
                )
            else:
                consecutive_errors = 0

            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                break
            continue

        if analytical_request and not had_tool_call:
            return _result(
                "contract_error",
                "Аналитический запрос требует хотя бы одного вызова run_python.",
                steps,
                files_by_path,
            )

        missing_extensions = missing_file_extensions(files_by_path, required_extensions)
        if last_tool_failed:
            messages.append({"role": "user", "content": build_incomplete_answer_message()})
            continue
        if missing_extensions:
            messages.append(
                {
                    "role": "user",
                    "content": build_missing_artifacts_message(missing_extensions),
                }
            )
            continue

        final_text = (response.content or "").strip()
        if not final_text:
            messages.append({"role": "user", "content": build_incomplete_answer_message()})
            continue

        if had_tool_call and needs_finalization(final_text):
            try:
                finalized = finalize_user_answer(
                    llm,
                    messages,
                    final_text,
                    files_by_path,
                )
                if is_usable_finalization(finalized):
                    final_text = finalized
                    steps.append(
                        AgentStep(
                            step_index=step_index + 1,
                            type="llm",
                            content={"content": final_text, "tool_calls": []},
                        )
                    )
            except LlmClientError:
                pass

        return _result("success", final_text, steps, files_by_path)

    cancelled = _cancelled(should_cancel, steps, files_by_path)
    if cancelled:
        return cancelled

    missing_extensions = missing_file_extensions(files_by_path, required_extensions)
    failure_note = None
    if last_tool_failed:
        failure_note = "последние попытки выполнения кода завершились ошибкой"
    elif missing_extensions:
        failure_note = (
            "не удалось создать запрошенные файлы форматов "
            + ", ".join(sorted(missing_extensions))
        )

    try:
        final_text = finalize_user_answer(
            llm,
            messages,
            "",
            files_by_path,
            failure_note=failure_note,
        )
    except LlmClientError:
        final_text = ""

    if not is_usable_finalization(final_text):
        return _result(
            "max_steps",
            "Достигнут максимальный предел шагов без завершенного ответа.",
            steps,
            files_by_path,
        )

    steps.append(
        AgentStep(
            step_index=max_steps + 1,
            type="llm",
            content={"content": final_text, "tool_calls": []},
        )
    )
    status = "error" if failure_note else "success"
    return _result(status, final_text, steps, files_by_path)
