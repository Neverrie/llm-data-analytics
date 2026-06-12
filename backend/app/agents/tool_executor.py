from dataclasses import dataclass
from typing import Any

from app.mcp.models import McpToolCall, McpToolResult
from app.mcp.server import McpToolServer

MAX_TOOL_CODE_CHARS = 4500
MAX_TOOL_CODE_LINES = 100


@dataclass
class ToolExecution:
    arguments: dict[str, Any]
    result: McpToolResult


def execute_tool_call(
    server: McpToolServer,
    tool_name: str,
    tool_arguments: dict[str, Any],
    call_id: str | None,
    dataset_path: str | None,
    run_id: str,
    call_index: int,
) -> ToolExecution:
    arguments = dict(tool_arguments)
    if dataset_path and "dataset_path" not in arguments:
        arguments["dataset_path"] = dataset_path
    arguments["run_id"] = run_id

    if call_index > 0:
        return ToolExecution(
            arguments=arguments,
            result=_error_result(
                call_id,
                tool_name,
                "За один ответ модели разрешён только один вызов инструмента. "
                "Если действие всё ещё нужно, выполни его следующим шагом.",
            ),
        )

    code = str(arguments.get("code") or "")
    line_count = len(code.splitlines())
    if tool_name == "run_python" and (
        len(code) > MAX_TOOL_CODE_CHARS or line_count > MAX_TOOL_CODE_LINES
    ):
        return ToolExecution(
            arguments=arguments,
            result=_error_result(
                call_id,
                tool_name,
                f"Python-скрипт слишком большой: {len(code)} символов, {line_count} строк. "
                f"Раздели работу на один сфокусированный шаг до {MAX_TOOL_CODE_CHARS} символов "
                f"и {MAX_TOOL_CODE_LINES} строк.",
            ),
        )

    return ToolExecution(
        arguments=arguments,
        result=server.call_tool(McpToolCall(name=tool_name, arguments=arguments, call_id=call_id)),
    )


def _error_result(call_id: str | None, tool_name: str, message: str) -> McpToolResult:
    return McpToolResult(
        call_id=call_id,
        name=tool_name,
        status="error",
        content={
            "sandbox_status": "error",
            "stdout": "",
            "stderr": message,
            "files": [],
            "elapsed_seconds": 0.0,
            "exit_code": None,
        },
        error=message,
    )
