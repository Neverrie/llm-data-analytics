from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.schemas import Lab3AskRequest, Lab3MapColumnsRequest, Lab3ResetSessionRequest, Lab3RunToolRequest
from app.services.lab2_service import Lab2PipelineError
from app.services.lab3_service import (
    ask_agent,
    clear_session,
    debug_openrouter_ping,
    get_current_status,
    get_datasets,
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
async def lab3_ask(request: Lab3AskRequest) -> dict:
    try:
        logger.info(
            "LAB3_ASK_START dataset=%s mode=%s question_len=%s",
            request.dataset_name,
            request.analysis_mode,
            len(request.question or ""),
        )
        return await ask_agent(
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
    except Lab2PipelineError as exc:
        logger.exception("LAB3_ASK_ERROR detail=%s", exc.message)
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


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


@router.get("/debug/openrouter-ping")
async def lab3_debug_openrouter_ping() -> dict:
    try:
        return await debug_openrouter_ping()
    except Lab2PipelineError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/current-status")
def lab3_current_status() -> dict:
    return get_current_status()
