from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.config import settings
from app.schemas import Lab2RunRequest, Lab2RunResponse, Lab2SampleDataResponse, Lab2StatusResponse
from app.services.lab2_service import Lab2PipelineError, find_dataset_file, get_sample_data, load_last_result, run_pipeline

router = APIRouter(prefix="/lab2", tags=["lab2"])


@router.get("/status", response_model=Lab2StatusResponse)
def lab2_status() -> Lab2StatusResponse:
    try:
        dataset_file = find_dataset_file().name
    except Lab2PipelineError:
        dataset_file = f"not found (expected base name: {settings.lab2_dataset_filename})"

    return Lab2StatusResponse(
        lab=2,
        name="API Pipeline",
        status="ready",
        dataset=dataset_file,
        model=settings.ollama_model,
        pipeline=[
            "read dataset",
            "filter reviews",
            "build prompt",
            "call Ollama API",
            "parse JSON",
            "validate with Pydantic",
            "save result.json",
        ],
        available_endpoints=[
            "GET /api/lab2/status",
            "GET /api/lab2/sample-data",
            "POST /api/lab2/run",
            "GET /api/lab2/result",
            "GET /api/lab2/download",
        ],
    )


@router.get("/sample-data", response_model=Lab2SampleDataResponse)
def lab2_sample_data(
    limit: int = Query(default=5, ge=1, le=50),
    min_score: int | None = Query(default=None, ge=1, le=5),
    max_score: int | None = Query(default=None, ge=1, le=5),
) -> Lab2SampleDataResponse:
    try:
        return get_sample_data(limit=limit, min_score=min_score, max_score=max_score)
    except Lab2PipelineError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/run", response_model=Lab2RunResponse)
async def lab2_run(request: Lab2RunRequest) -> Lab2RunResponse:
    try:
        return await run_pipeline(request)
    except Lab2PipelineError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/result", response_model=Lab2RunResponse)
def lab2_result() -> Lab2RunResponse:
    try:
        return load_last_result()
    except Lab2PipelineError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/download")
def lab2_download() -> FileResponse:
    output_path = Path(settings.outputs_dir) / "lab2_result.json"
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Result file does not exist yet. Run /api/lab2/run first.")

    return FileResponse(
        output_path,
        media_type="application/json",
        filename="lab2_result.json",
    )
