from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import settings
from app.ollama_client import OllamaClient, OllamaClientError
from app.schemas import (
    Lab2ResultPayload,
    Lab2RunRequest,
    Lab2RunResponse,
    Lab2SampleDataResponse,
    ReviewClassification,
    UberReviewInput,
)


class Lab2PipelineError(RuntimeError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _to_str_or_none(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _to_int_or_none(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def find_dataset_file() -> Path:
    datasets_dir = Path(settings.datasets_dir)
    filename = settings.lab2_dataset_filename

    candidate_stems = [filename]
    if filename == "customer_reviews":
        candidate_stems.append("customers_reviews")

    candidates: list[Path] = []
    for stem in candidate_stems:
        candidates.extend(
            [
                datasets_dir / stem,
                datasets_dir / f"{stem}.csv",
                datasets_dir / f"{stem}.xlsx",
            ]
        )

    for path in candidates:
        if path.exists() and path.is_file():
            return path

    available = sorted(str(path.name) for path in datasets_dir.glob("*"))
    looked = ", ".join(str(path) for path in candidates)
    raise Lab2PipelineError(
        "Dataset file was not found. "
        f"Looked for: {looked}. Available files in datasets: {available}",
        status_code=404,
    )


def _read_dataset(dataset_path: Path) -> pd.DataFrame:
    suffix = dataset_path.suffix.lower()
    try:
        if suffix == ".csv":
            return pd.read_csv(dataset_path)
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(dataset_path)
        try:
            return pd.read_csv(dataset_path)
        except Exception:
            return pd.read_excel(dataset_path)
    except Exception as exc:
        raise Lab2PipelineError(f"Failed to read dataset: {dataset_path}. Error: {exc}") from exc


def load_uber_reviews(
    limit: int | None,
    min_score: int | None,
    max_score: int | None,
) -> tuple[str, int, list[UberReviewInput]]:
    dataset_path = find_dataset_file()
    frame = _read_dataset(dataset_path)

    if "content" not in frame.columns:
        raise Lab2PipelineError(
            "Dataset does not contain required 'content' column. "
            f"Found columns: {list(frame.columns)}"
        )

    if min_score is not None or max_score is not None:
        score_series = pd.to_numeric(frame.get("score"), errors="coerce")
        if min_score is not None:
            frame = frame[score_series >= min_score]
            score_series = pd.to_numeric(frame.get("score"), errors="coerce")
        if max_score is not None:
            frame = frame[score_series <= max_score]

    rows: list[UberReviewInput] = []
    for row_index, row in frame.iterrows():
        content = _to_str_or_none(row.get("content"))
        if not content:
            continue

        review = UberReviewInput(
            row_id=int(row_index) + 1,
            content=content,
            score=(None if pd.isna(row.get("score")) else row.get("score")),
            thumbs_up_count=_to_int_or_none(row.get("thumbsUpCount")),
            review_created_version=_to_str_or_none(row.get("reviewCreatedVersion")),
            at=_to_str_or_none(row.get("at")),
            app_version=_to_str_or_none(row.get("appVersion")),
        )
        rows.append(review)

    total_rows = len(rows)
    if limit is not None:
        rows = rows[:limit]

    return dataset_path.name, total_rows, rows


def build_lab2_prompt(reviews: list[UberReviewInput]) -> str:
    reviews_json = json.dumps([review.model_dump() for review in reviews], ensure_ascii=False, indent=2)
    return f"""You are an analyst of Uber mobile app user reviews.

You receive real user reviews.
For each review, determine:
- sentiment: positive, negative, neutral, or mixed
- issue_type: short English snake_case label
- topic: main English snake_case topic
- urgency: low, medium, or high
- summary: short summary in Russian language
- suggested_action: short actionable recommendation in Russian language

Return only valid JSON. No markdown and no explanations.

Strict format:
{{
  "results": [
    {{
      "row_id": 1,
      "sentiment": "negative",
      "issue_type": "payment_issue",
      "topic": "billing",
      "urgency": "high",
      "summary": "Short Russian summary.",
      "suggested_action": "Short Russian action."
    }}
  ]
}}

Rules:
- Do not invent reviews.
- Use only provided row_id values.
- Return output for every provided review.
- If a review is short or unclear, use sentiment neutral or mixed.
- If score is low and text contains complaint, urgency may be high.
- If score is high and feedback is positive, urgency is usually low.
- Do not include personal data.
- Do not include userName or userImage.

Input reviews:
{reviews_json}
"""


def parse_llm_json(text: str) -> Any:
    cleaned = text.strip()

    fenced_match = re.search(r"```json\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fenced_match:
        cleaned = fenced_match.group(1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        maybe_json = cleaned[start : end + 1]
        try:
            return json.loads(maybe_json)
        except json.JSONDecodeError:
            pass

    preview = cleaned[:500]
    raise Lab2PipelineError(f"LLM returned invalid JSON. Response preview: {preview}")


def validate_result(parsed_json: Any, expected_row_ids: set[int]) -> list[ReviewClassification]:
    normalized: dict[str, Any]
    if isinstance(parsed_json, dict) and "results" in parsed_json:
        normalized = parsed_json
    elif isinstance(parsed_json, list):
        normalized = {"results": parsed_json}
    elif isinstance(parsed_json, dict):
        alt_keys = ("items", "data", "classifications", "reviews")
        alt_key = next((key for key in alt_keys if isinstance(parsed_json.get(key), list)), None)
        if alt_key is not None:
            normalized = {"results": parsed_json[alt_key]}
        elif "row_id" in parsed_json:
            normalized = {"results": [parsed_json]}
        else:
            preview = json.dumps(parsed_json, ensure_ascii=False)[:500]
            raise Lab2PipelineError(
                f"LLM response does not contain 'results' field. Parsed object preview: {preview}"
            )
    else:
        raise Lab2PipelineError("LLM response JSON must be an object or array.")

    payload = Lab2ResultPayload.model_validate(normalized)
    results = payload.results

    returned_ids = {item.row_id for item in results}
    unknown_ids = sorted(returned_ids - expected_row_ids)
    missing_ids = sorted(expected_row_ids - returned_ids)

    if unknown_ids:
        raise Lab2PipelineError(f"LLM returned unknown row_id values: {unknown_ids}")
    if missing_ids:
        raise Lab2PipelineError(f"LLM missed row_id values: {missing_ids}")

    return results


def save_result(result: Lab2RunResponse) -> Path:
    outputs_dir = Path(settings.outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    output_path = outputs_dir / "lab2_result.json"
    output_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return output_path


def load_last_result() -> Lab2RunResponse:
    output_path = Path(settings.outputs_dir) / "lab2_result.json"
    if not output_path.exists():
        raise Lab2PipelineError("Result file does not exist yet. Run /api/lab2/run first.", status_code=404)

    try:
        return Lab2RunResponse.model_validate_json(output_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise Lab2PipelineError(f"Saved result is invalid JSON: {exc}") from exc


async def run_pipeline(request: Lab2RunRequest) -> Lab2RunResponse:
    if request.min_score is not None and request.max_score is not None and request.min_score > request.max_score:
        raise Lab2PipelineError("min_score cannot be greater than max_score.")

    dataset_name, _, reviews = load_uber_reviews(
        limit=request.limit,
        min_score=request.min_score,
        max_score=request.max_score,
    )
    if not reviews:
        raise Lab2PipelineError("No reviews found after filtering.")

    prompt = build_lab2_prompt(reviews)
    client = OllamaClient(settings.ollama_base_url)

    try:
        llm_response = await client.generate_json(settings.ollama_model, prompt)
    except OllamaClientError as exc:
        raise Lab2PipelineError(str(exc), status_code=503) from exc

    parsed = parse_llm_json(llm_response.response)
    validated = validate_result(parsed, expected_row_ids={review.row_id for review in reviews})

    response = Lab2RunResponse(
        lab=2,
        status="completed",
        model=settings.ollama_model,
        dataset=dataset_name,
        rows_processed=len(validated),
        output_file=str((Path(settings.outputs_dir) / "lab2_result.json")),
        results=validated,
    )
    save_result(response)
    return response


def get_sample_data(limit: int, min_score: int | None, max_score: int | None) -> Lab2SampleDataResponse:
    if min_score is not None and max_score is not None and min_score > max_score:
        raise Lab2PipelineError("min_score cannot be greater than max_score.")

    dataset_name, total_rows, rows = load_uber_reviews(limit=limit, min_score=min_score, max_score=max_score)
    return Lab2SampleDataResponse(dataset=dataset_name, total_rows=total_rows, sample=rows)
