from __future__ import annotations

import json
import math
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

MAX_LIMIT = 100


class Lab2PipelineError(RuntimeError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def find_dataset_file() -> Path:
    datasets_dir = Path(settings.datasets_dir)
    filename = settings.lab2_dataset_filename

    candidate_stems = [filename]
    if filename == "customer_reviews":
        candidate_stems.append("customers_reviews")

    candidates: list[Path] = []
    for stem in candidate_stems:
        candidates.extend([datasets_dir / stem, datasets_dir / f"{stem}.csv", datasets_dir / f"{stem}.xlsx"])

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


def normalize_score(value: Any) -> int | None:
    if value is None or (isinstance(value, float) and math.isnan(value)) or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return int(value)

    text = str(value).strip()
    if not text:
        return None
    try:
        numeric = float(text)
    except ValueError:
        return None
    return int(numeric)


def _normalize_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _normalize_str(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


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

    working = frame.copy()
    working["_normalized_score"] = working.get("score").apply(normalize_score)

    if min_score is not None:
        working = working[working["_normalized_score"].notna() & (working["_normalized_score"] >= min_score)]
    if max_score is not None:
        working = working[working["_normalized_score"].notna() & (working["_normalized_score"] <= max_score)]

    rows: list[UberReviewInput] = []
    for row_index, row in working.iterrows():
        content = _normalize_str(row.get("content"))
        if not content:
            continue

        rows.append(
            UberReviewInput(
                row_id=int(row_index) + 1,
                content=content,
                score=normalize_score(row.get("_normalized_score")),
                thumbs_up_count=_normalize_int(row.get("thumbsUpCount")),
                review_created_version=_normalize_str(row.get("reviewCreatedVersion")),
                at=_normalize_str(row.get("at")),
                app_version=_normalize_str(row.get("appVersion")),
            )
        )

    total_rows = len(rows)
    if limit is not None:
        rows = rows[:limit]

    return dataset_path.name, total_rows, rows


def build_lab2_prompt(reviews: list[UberReviewInput]) -> str:
    reviews_json = json.dumps([review.model_dump() for review in reviews], ensure_ascii=False, indent=2)
    return f"""Ты аналитик пользовательских отзывов приложения Uber.

Тебе переданы отзывы пользователей в JSON.
Каждый отзыв содержит:
- row_id
- content
- score
- thumbs_up_count
- review_created_version
- at
- app_version

Твоя задача — классифицировать каждый отзыв.

Верни строго один JSON-объект без markdown, без комментариев и без текста вокруг.

Строгий формат:
{{
  "results": [
    {{
      "row_id": 1,
      "sentiment": "negative",
      "issue_type": "payment_issue",
      "topic": "billing",
      "urgency": "high",
      "summary": "Пользователь жалуется на проблему с оплатой.",
      "suggested_action": "Проверить сценарии оплаты и возврата средств."
    }}
  ]
}}

Разрешенные значения sentiment:
- positive
- negative
- neutral
- mixed

Разрешенные значения urgency:
- low
- medium
- high

Правила:
- Верни результат для каждого переданного row_id.
- Используй только переданные row_id.
- Не добавляй score в результат.
- Не добавляй content в результат.
- Не добавляй userName, userImage или персональные данные.
- score — это только дополнительный входной сигнал.
- Если score отсутствует, классифицируй только по content.
- Если score низкий и текст содержит жалобу, urgency обычно high или medium.
- Если score высокий и текст положительный, urgency обычно low.
- Если отзыв короткий или неясный, используй neutral или mixed.
- issue_type и topic пиши на английском snake_case.
- summary и suggested_action пиши на русском языке.
- Не выдумывай факты, которых нет в отзыве.

Данные:
{reviews_json}
"""


def parse_llm_json(text: str) -> Any:
    cleaned = text.strip()

    fenced_match = re.search(r"```json\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fenced_match:
        cleaned = fenced_match.group(1).strip()

    def _loads(value: str) -> Any:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    parsed = _loads(cleaned)
    if parsed is not None:
        return parsed

    start = cleaned.find("{")
    if start != -1:
        depth = 0
        for idx in range(start, len(cleaned)):
            char = cleaned[idx]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    parsed = _loads(cleaned[start : idx + 1])
                    if parsed is not None:
                        return parsed
                    break

    preview = cleaned[:500]
    raise Lab2PipelineError(f"LLM returned invalid JSON. Response preview: {preview}")


def _normalize_classification_fields(item: ReviewClassification) -> ReviewClassification:
    issue_type = (item.issue_type or "").strip() or "unknown"
    topic = (item.topic or "").strip() or "unknown"
    summary = (item.summary or "").strip() or "Нет данных"
    suggested_action = (item.suggested_action or "").strip() or "Проверить отзыв вручную"
    return item.model_copy(
        update={
            "issue_type": issue_type,
            "topic": topic,
            "summary": summary,
            "suggested_action": suggested_action,
        }
    )


def validate_result(parsed_json: Any, expected_row_ids: set[int]) -> list[ReviewClassification]:
    if isinstance(parsed_json, dict) and "error" in parsed_json and "results" not in parsed_json:
        preview = json.dumps(parsed_json, ensure_ascii=False)[:500]
        raise Lab2PipelineError(
            "LLM returned an error object instead of classification results. "
            f"Response preview: {preview}"
        )

    if not isinstance(parsed_json, dict):
        raise Lab2PipelineError("LLM response JSON must be an object.")
    if "results" not in parsed_json:
        preview = json.dumps(parsed_json, ensure_ascii=False)[:500]
        raise Lab2PipelineError(f"LLM response does not contain 'results' field. Parsed object preview: {preview}")
    if not isinstance(parsed_json["results"], list):
        raise Lab2PipelineError("LLM field 'results' must be a list.")

    payload = Lab2ResultPayload.model_validate(parsed_json)
    normalized_results = [_normalize_classification_fields(item) for item in payload.results]

    returned_ids = [item.row_id for item in normalized_results]
    duplicate_ids = sorted({row_id for row_id in returned_ids if returned_ids.count(row_id) > 1})
    if duplicate_ids:
        raise Lab2PipelineError(f"LLM returned duplicate row_id values: {duplicate_ids}")

    returned_set = set(returned_ids)
    unknown_ids = sorted(returned_set - expected_row_ids)
    missing_ids = sorted(expected_row_ids - returned_set)

    if unknown_ids:
        raise Lab2PipelineError(f"LLM returned unknown row_id values: {unknown_ids}")
    if missing_ids:
        raise Lab2PipelineError(f"LLM missed row_id values: {missing_ids}")

    return normalized_results


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


def _chunk_reviews(reviews: list[UberReviewInput], batch_size: int) -> list[list[UberReviewInput]]:
    return [reviews[index : index + batch_size] for index in range(0, len(reviews), batch_size)]


async def run_pipeline(request: Lab2RunRequest) -> Lab2RunResponse:
    if request.min_score is not None and request.max_score is not None and request.min_score > request.max_score:
        raise Lab2PipelineError("min_score cannot be greater than max_score.")

    warnings: list[str] = []
    effective_limit = request.limit
    if request.limit > MAX_LIMIT:
        effective_limit = MAX_LIMIT
        warnings.append(f"limit was capped to MAX_LIMIT={MAX_LIMIT}. Requested: {request.limit}.")

    dataset_name, _, reviews = load_uber_reviews(
        limit=effective_limit,
        min_score=request.min_score,
        max_score=request.max_score,
    )
    if not reviews:
        raise Lab2PipelineError("No reviews found after filtering.")

    batches = _chunk_reviews(reviews, request.batch_size)
    client = OllamaClient(settings.ollama_base_url)

    combined_results: list[ReviewClassification] = []
    for batch in batches:
        prompt = build_lab2_prompt(batch)
        try:
            llm_response = await client.generate_json(settings.ollama_model, prompt)
        except OllamaClientError as exc:
            raise Lab2PipelineError(str(exc), status_code=503) from exc

        parsed = parse_llm_json(llm_response.response)
        validated_batch = validate_result(parsed, expected_row_ids={review.row_id for review in batch})
        combined_results.extend(validated_batch)

    all_expected_ids = {review.row_id for review in reviews}
    all_returned_ids = [item.row_id for item in combined_results]
    if len(all_returned_ids) != len(set(all_returned_ids)):
        raise Lab2PipelineError("Duplicate row_id detected after batch merge.")
    if set(all_returned_ids) != all_expected_ids:
        missing = sorted(all_expected_ids - set(all_returned_ids))
        unknown = sorted(set(all_returned_ids) - all_expected_ids)
        raise Lab2PipelineError(f"Merged results mismatch. Missing: {missing}, Unknown: {unknown}")

    combined_results.sort(key=lambda item: item.row_id)
    response = Lab2RunResponse(
        lab=2,
        status="completed",
        model=settings.ollama_model,
        dataset=dataset_name,
        rows_requested=request.limit,
        rows_processed=len(combined_results),
        batch_size=request.batch_size,
        batches_processed=len(batches),
        output_file=str((Path(settings.outputs_dir) / "lab2_result.json")),
        warnings=warnings,
        results=combined_results,
    )
    save_result(response)
    return response


def get_sample_data(limit: int, min_score: int | None, max_score: int | None) -> Lab2SampleDataResponse:
    if min_score is not None and max_score is not None and min_score > max_score:
        raise Lab2PipelineError("min_score cannot be greater than max_score.")

    capped_limit = min(limit, MAX_LIMIT)
    dataset_name, total_rows, rows = load_uber_reviews(limit=capped_limit, min_score=min_score, max_score=max_score)
    return Lab2SampleDataResponse(dataset=dataset_name, total_rows=total_rows, sample=rows)
