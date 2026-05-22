import json
from pathlib import Path
from typing import Any, Callable

from app.agents.models import AgentResult, AgentStep
from app.llm.client import LlmClient, LlmClientError
from app.llm.models import LlmMessage
from app.mcp.models import McpToolCall
from app.mcp.server import McpToolServer

SOFT_STEP_TARGET = 8
SOFT_FILE_TARGET = 6


def _is_analytical_request(text: str) -> bool:
    low = (text or "").lower()
    keywords = ["анализ", "проанализ", "граф", "chart", "plot", "dataset", "датасет", "таблиц", "сводк", "статист", "csv"]
    return any(k in low for k in keywords)


def _dataset_instruction(dataset_path: str | None) -> str:
    if not dataset_path:
        return ""
    return (
        "Dataset is mounted at /input/dataset.csv. "
        "For any analysis, call run_python. "
        "Save all generated files only inside /work (example: /work/report.md, /work/chart.png). "
        "If a Python package is missing, you may install it with pip inside the script using: "
        "`python -m pip install --user <package>` and then continue execution. "
        "Do not use /outputs, /root, docker commands, or IPython-only modules. "
        "Keep artifacts minimal: generate only important final files, prefer overwriting stable filenames "
        "(for example /work/eda_report.md, /work/summary.csv, /work/main_chart.png) instead of creating many variants."
    )


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
    mcp = McpToolServer()
    tools = mcp.list_tools()

    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are a data analysis assistant. "
                "Use tool calls when calculations, charts, or dataset operations are needed. "
                "Never claim execution without calling tools. "
                + _dataset_instruction(dataset_path)
            ).strip(),
        },
    ]
    messages.append(
        {
            "role": "system",
            "content": (
                "If conversation memory is provided, continue from it and avoid redoing completed work. "
                "Prefer updating existing artifacts instead of generating many new files."
            ),
        }
    )
    if conversation_context:
        messages.append({"role": "system", "content": f"Conversation memory:\n{conversation_context}"})
    if existing_artifacts:
        artifact_lines: list[str] = []
        for art in existing_artifacts[:30]:
            title = str(art.get("title") or art.get("filename") or "artifact")
            fname = str(art.get("filename") or "")
            kind = str(art.get("kind") or "")
            artifact_lines.append(f"- {title} ({kind}) file={fname}")
        if artifact_lines:
            messages.append(
                {
                    "role": "system",
                    "content": "Existing artifacts in this chat (reuse/overwrite when possible):\n" + "\n".join(artifact_lines),
                }
            )
    messages.append({"role": "user", "content": user_message})

    steps: list[AgentStep] = []
    all_files: list[dict[str, Any]] = []
    had_tool_call = False
    soft_limit_reminded = False
    file_limit_reminded = False

    for idx in range(1, max_steps + 1):
        if idx > SOFT_STEP_TARGET and not soft_limit_reminded:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        f"Soft guidance: you already used {idx - 1} steps. "
                        "Prefer to finish now with final answer. Continue only if one truly necessary tool call remains."
                    ),
                }
            )
            soft_limit_reminded = True
        if should_cancel and should_cancel():
            return AgentResult(final_answer="Run cancelled by user.", steps=steps, files=all_files, status="cancelled")
        try:
            llm_resp = llm.chat(messages=[LlmMessage.model_validate(m) for m in messages], tools=tools)
        except LlmClientError as exc:
            return AgentResult(final_answer=str(exc), steps=steps, files=all_files, status="error")

        steps.append(AgentStep(step_index=idx, type="llm", content={"content": llm_resp.content, "tool_calls": [tc.model_dump() for tc in llm_resp.tool_calls]}))
        if on_event:
            on_event(
                {
                    "stage": "llm_step",
                    "step": idx,
                    "tool_calls": len(llm_resp.tool_calls),
                    "message": f"LLM step {idx}: tool calls={len(llm_resp.tool_calls)}",
                }
            )

        if llm_resp.tool_calls:
            had_tool_call = True
            messages.append(
                {
                    "role": "assistant",
                    "content": llm_resp.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id or f"call-{idx}",
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.arguments, ensure_ascii=False)},
                        }
                        for tc in llm_resp.tool_calls
                    ],
                }
            )

            for tc in llm_resp.tool_calls:
                if should_cancel and should_cancel():
                    return AgentResult(final_answer="Run cancelled by user.", steps=steps, files=all_files, status="cancelled")
                args = dict(tc.arguments)
                if dataset_path and "dataset_path" not in args:
                    args["dataset_path"] = dataset_path
                tool_result = mcp.call_tool(McpToolCall(name=tc.name, arguments=args, call_id=tc.id))
                files = tool_result.content.get("files") or []
                if isinstance(files, list):
                    for f in files:
                        if isinstance(f, dict):
                            all_files.append(f)
                if len(all_files) > SOFT_FILE_TARGET and not file_limit_reminded:
                    messages.append(
                        {
                            "role": "system",
                            "content": (
                                f"Soft guidance: you already generated more than {SOFT_FILE_TARGET} files. "
                                "Stop producing extra artifacts, reuse/overwrite existing filenames, and finalize."
                            ),
                        }
                    )
                    file_limit_reminded = True

                steps.append(
                    AgentStep(
                        step_index=idx,
                        type="tool",
                        content={
                            "tool_name": tc.name,
                            "tool_arguments": args,
                            "result": tool_result.model_dump(),
                        },
                    )
                )
                if on_event:
                    tool_payload = tool_result.content if isinstance(tool_result.content, dict) else {}
                    on_event(
                        {
                            "stage": "tool_result",
                            "step": idx,
                            "message": f"Tool {tc.name} finished",
                            "sandbox_status": tool_payload.get("sandbox_status") or tool_result.status,
                            "elapsed_seconds": tool_payload.get("elapsed_seconds"),
                            "error": tool_result.error,
                        }
                    )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": json.dumps(tool_result.content, ensure_ascii=False),
                    }
                )
            continue

        if _is_analytical_request(user_message) and not had_tool_call:
            return AgentResult(final_answer="Analytical request requires at least one run_python tool call.", steps=steps, files=all_files, status="contract_error")

        return AgentResult(final_answer=llm_resp.content, steps=steps, files=all_files, status="success")

    # Finalization pass: force model to summarize based on collected tool outputs.
    try:
        if should_cancel and should_cancel():
            return AgentResult(final_answer="Run cancelled by user.", steps=steps, files=all_files, status="cancelled")
        finalize_messages = [
            *messages,
            {
                "role": "system",
                "content": (
                    "Stop calling tools. Provide a final user-facing answer now. "
                    "Summarize key findings, mention important caveats from stderr if any, "
                    "and reference generated files if present."
                ),
            },
        ]
        final_resp = llm.chat(messages=[LlmMessage.model_validate(m) for m in finalize_messages], tools=None)
        final_text = (final_resp.content or "").strip() or "Готово. Анализ выполнен, см. шаги и артефакты."
        steps.append(
            AgentStep(
                step_index=max_steps + 1,
                type="llm",
                content={"content": final_text, "tool_calls": []},
            )
        )
        return AgentResult(final_answer=final_text, steps=steps, files=all_files, status="success")
    except Exception:
        return AgentResult(final_answer="Max steps reached before final answer", steps=steps, files=all_files, status="max_steps")

