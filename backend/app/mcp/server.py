import json

from app.mcp.models import McpToolCall, McpToolResult, RunPythonArgs
from app.mcp.tools import SandboxTools


class McpToolServer:
    def __init__(self):
        self.tools = SandboxTools()

    def list_tools(self) -> list[dict]:
        return [
            {
                "name": "run_python",
                "description": (
                    "Execute one focused Python action in an isolated Docker sandbox. "
                    "Dataset is available as /input/dataset.csv if provided. "
                    "Use /work for persistent files and prefer small incremental calls."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "dataset_path": {"type": "string", "nullable": True},
                        "run_id": {"type": "string", "nullable": True},
                    },
                    "required": ["code"],
                },
            }
        ]

    def call_tool(self, call: McpToolCall) -> McpToolResult:
        if call.name == "run_python":
            raw_args = dict(call.arguments or {})
            if "parameters" in raw_args and isinstance(raw_args.get("parameters"), str):
                try:
                    parsed = json.loads(raw_args["parameters"])
                    if isinstance(parsed, dict):
                        raw_args = parsed
                except Exception:
                    pass
            elif "parameters" in raw_args and isinstance(raw_args.get("parameters"), dict):
                raw_args = raw_args["parameters"]
            elif "arguments" in raw_args and isinstance(raw_args.get("arguments"), dict):
                raw_args = raw_args["arguments"]

            args = RunPythonArgs.model_validate(raw_args)
            result = self.tools.run_python(args)
            result.call_id = call.call_id
            return result

        return McpToolResult(
            call_id=call.call_id,
            name=call.name,
            status="error",
            content={},
            error=f"Unknown tool: {call.name}",
        )
