from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from app.schemas import Lab3AskRequest, Lab3MapColumnsRequest, Lab3ResetSessionRequest, Lab3RunToolRequest
from app.services.artifact_service import register_result_artifacts
from app.services.auth_service import get_current_user
from app.services.lab2_service import Lab2PipelineError
from app.services.lab3_service import (
    ask_agent,
    clear_session,
    debug_openrouter_ping,
    get_current_status,
    get_datasets,
    get_generated_file_path,
    get_lab3_status,
    get_last_result,
    get_profile,
    get_report_path,
    get_session_state,
    get_tools,
    map_columns,
    run_tool,
    upload_dataset,
)
from app.stream_events import StreamEmitter, chunk_text_for_streaming

router = APIRouter(prefix="/lab3", tags=["lab3"])
logger = logging.getLogger(__name__)


@router.get("/status")
def lab3_status() -> dict:
    return get_lab3_status()


@router.get("/datasets")
def lab3_datasets() -> dict:
    return get_datasets()


@router.post("/upload-dataset")
async def lab3_upload_dataset(file: UploadFile = File(...)) -> dict:
    try:
        return await upload_dataset(file)
    except Lab2PipelineError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/profile")
async def lab3_profile(dataset_name: str = Query(...)) -> dict:
    try:
        return await get_profile(dataset_name)
    except Lab2PipelineError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/map-columns")
async def lab3_map_columns(request: Lab3MapColumnsRequest) -> dict:
    try:
        return await map_columns(request.dataset_name, request.user_overrides)
    except Lab2PipelineError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/tools")
def lab3_tools() -> dict:
    return get_tools()


@router.post("/run-tool")
async def lab3_run_tool(request: Lab3RunToolRequest) -> dict:
    try:
        return await run_tool(
            dataset_name=request.dataset_name,
            tool=request.tool,
            arguments=request.arguments,
            column_overrides=request.column_overrides,
        )
    except Lab2PipelineError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/ask")
async def lab3_ask(request: Lab3AskRequest, user: dict = Depends(get_current_user)) -> dict:
    try:
        logger.info(
            "LAB3_ASK_START dataset=%s mode=%s question_len=%s",
            request.dataset_name,
            request.analysis_mode,
            len(request.question or ""),
        )
        result = await ask_agent(
            dataset_name=request.dataset_name,
            question=request.question,
            column_overrides=request.column_overrides,
            max_tool_calls=request.max_tool_calls,
            use_critic=request.use_critic,
            analysis_mode=request.analysis_mode,
            session_id=request.session_id,
            include_history=request.include_history,
            reset_session_flag=request.reset_session,
            max_code_steps=request.max_code_steps,
        )
        result["artifacts"] = register_result_artifacts(
            user_id=user["id"],
            result=result,
            chat_id=request.chat_id,
            message_id=request.message_id,
            source="lab3",
        )
        return result
    except Lab2PipelineError as exc:
        logger.exception("LAB3_ASK_ERROR detail=%s", exc.message)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/ask/stream")
async def lab3_ask_stream(request: Lab3AskRequest, user: dict = Depends(get_current_user)):
    async def event_generator():
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def sender(payload: str) -> None:
            await queue.put(payload)

        emitter = StreamEmitter(sender=sender)

        async def worker() -> None:
            heartbeat_task: asyncio.Task | None = None

            async def heartbeat() -> None:
                hints = [
                    "Планирую шаги анализа...",
                    "Проверяю структуру данных...",
                    "Готовлю и запускаю вычисления...",
                    "Собираю таблицы и графики...",
                ]
                idx = 0
                while True:
                    await asyncio.sleep(4)
                    await emitter.emit("tool_log", {"content": hints[idx % len(hints)]})
                    idx += 1

            try:
                await emitter.emit("message_start", {"role": "assistant", "dataset": request.dataset_name})
                await emitter.emit("tool_start", {"name": "lab3_agent"})
                await emitter.emit("tool_log", {"content": "Запускаю анализ..."})
                await emitter.emit("tool_log", {"content": "Обрабатываю запрос..."})
                heartbeat_task = asyncio.create_task(heartbeat())
                result = await ask_agent(
                    dataset_name=request.dataset_name,
                    question=request.question,
                    column_overrides=request.column_overrides,
                    max_tool_calls=request.max_tool_calls,
                    use_critic=request.use_critic,
                    analysis_mode=request.analysis_mode,
                    session_id=request.session_id,
                    include_history=request.include_history,
                    reset_session_flag=request.reset_session,
                    max_code_steps=request.max_code_steps,
                )
                artifacts = register_result_artifacts(
                    user_id=user["id"],
                    result=result,
                    chat_id=request.chat_id,
                    message_id=request.message_id,
                    source="lab3",
                )
                code_steps = result.get("code_steps") or result.get("steps") or []
                if isinstance(code_steps, list):
                    for step in code_steps:
                        if not isinstance(step, dict):
                            continue
                        step_no = step.get("step", "?")
                        exec_info = step.get("execution") if isinstance(step.get("execution"), dict) else {}
                        status = exec_info.get("status") or step.get("status") or "unknown"
                        await emitter.emit("tool_log", {"content": f"Шаг {step_no}: {status}"})
                        await emitter.emit("code_executed", {"step": step_no, "status": status})
                        code = str(step.get("code", "")).strip()
                        if code:
                            await emitter.emit(
                                "code_preview",
                                {
                                    "step": int(step.get("step") or step_no if str(step_no).isdigit() else 1),
                                    "language": "python",
                                    "preview": "\n".join(code.splitlines()[:12]),
                                    "code": code,
                                },
                            )
                            await emitter.emit("tool_log", {"content": f"Код шага {step_no}: {code[:220]}{'...' if len(code) > 220 else ''}"})

                for chunk in chunk_text_for_streaming(str(result.get("final_answer", ""))):
                    await emitter.emit("message_delta", {"content": chunk})

                for item in artifacts:
                    await emitter.emit(
                        "artifact_created",
                        {
                            "artifact_id": item.get("id"),
                            "kind": item.get("kind"),
                            "title": item.get("title"),
                            "filename": item.get("filename"),
                            "mime_type": item.get("mime_type"),
                            "preview_url": item.get("preview_url"),
                            "download_url": item.get("download_url"),
                        },
                    )

                await emitter.emit("tool_end", {"name": "lab3_agent", "status": "success"})
                await emitter.emit(
                    "done",
                    {
                        "status": "ok",
                        "analysis_mode": result.get("analysis_mode", request.analysis_mode),
                        "session_id": result.get("session_id"),
                    },
                )
            except Lab2PipelineError:
                logger.exception("LAB3_ASK_STREAM_ERROR")
                await emitter.emit("error", {"message": "Не удалось получить ответ модели"})
                await emitter.emit("done", {"status": "error"})
            except Exception:  # pragma: no cover
                logger.exception("LAB3_ASK_STREAM_UNEXPECTED_ERROR")
                await emitter.emit("error", {"message": "Не удалось получить ответ модели"})
                await emitter.emit("done", {"status": "error"})
            finally:
                if heartbeat_task and not heartbeat_task.done():
                    heartbeat_task.cancel()
                await queue.put(None)

        task = asyncio.create_task(worker())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.get("/session")
def lab3_session(session_id: str = Query(...)) -> dict:
    try:
        return get_session_state(session_id)
    except Lab2PipelineError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/reset-session")
def lab3_reset_session(request: Lab3ResetSessionRequest) -> dict:
    try:
        return clear_session(request.session_id)
    except Lab2PipelineError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/result")
def lab3_result() -> dict:
    try:
        return get_last_result()
    except Lab2PipelineError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/download-report")
def lab3_download_report() -> FileResponse:
    try:
        report_path = get_report_path()
    except Lab2PipelineError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return FileResponse(report_path, media_type="text/markdown", filename="lab3_report.md")


@router.get("/generated-file")
def lab3_generated_file(path: str = Query(...)) -> FileResponse:
    try:
        file_path = get_generated_file_path(path)
    except Lab2PipelineError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return FileResponse(file_path)


@router.get("/debug/openrouter-ping")
async def lab3_debug_openrouter_ping() -> dict:
    try:
        return await debug_openrouter_ping()
    except Lab2PipelineError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/current-status")
def lab3_current_status() -> dict:
    return get_current_status()
