from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.schemas import OllamaGenerateResponse, ReviewClassification
from app.services import lab2_service


@pytest.fixture
def temp_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    datasets_dir = tmp_path / "datasets"
    outputs_dir = tmp_path / "outputs"
    datasets_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "datasets_dir", str(datasets_dir))
    monkeypatch.setattr(settings, "outputs_dir", str(outputs_dir))
    monkeypatch.setattr(settings, "lab2_dataset_filename", "customer_reviews")
    monkeypatch.setattr(settings, "ollama_model", "qwen3:8b")
    return {"datasets_dir": datasets_dir, "outputs_dir": outputs_dir}


def _write_dataset(path: Path) -> None:
    frame = pd.DataFrame(
        [
            {
                "content": " Good app ",
                "score": "5",
                "thumbsUpCount": "2",
                "reviewCreatedVersion": "1.0",
                "at": "2024-01-01",
                "appVersion": "1.0",
            },
            {
                "content": "   ",
                "score": "4.0",
                "thumbsUpCount": "",
                "reviewCreatedVersion": None,
                "at": None,
                "appVersion": None,
            },
            {
                "content": "Bad support",
                "score": "not_a_number",
                "thumbsUpCount": "7",
                "reviewCreatedVersion": "1.2",
                "at": "2024-01-02",
                "appVersion": "1.2",
            },
            {
                "content": "Average",
                "score": 2,
                "thumbsUpCount": None,
                "reviewCreatedVersion": "1.3",
                "at": "2024-01-03",
                "appVersion": "1.3",
            },
        ]
    )
    frame.to_csv(path, index=False)


def test_score_normalization() -> None:
    assert lab2_service.normalize_score("5") == 5
    assert lab2_service.normalize_score("4.0") == 4
    assert lab2_service.normalize_score(3) == 3
    assert lab2_service.normalize_score("") is None
    assert lab2_service.normalize_score(None) is None
    assert lab2_service.normalize_score(float("nan")) is None


def test_load_uber_reviews(temp_paths: dict[str, Path]) -> None:
    dataset_path = temp_paths["datasets_dir"] / "customer_reviews.csv"
    _write_dataset(dataset_path)

    dataset, total_rows, rows = lab2_service.load_uber_reviews(limit=10, min_score=None, max_score=None)
    assert dataset == "customer_reviews.csv"
    assert total_rows == 3  # one empty content row was skipped
    assert len(rows) == 3
    assert rows[0].content == "Good app"
    assert rows[0].score == 5
    assert rows[0].thumbs_up_count == 2
    assert rows[1].score is None

    _, _, filtered_rows = lab2_service.load_uber_reviews(limit=10, min_score=4, max_score=5)
    assert len(filtered_rows) == 1
    assert filtered_rows[0].score == 5

    _, _, limited_rows = lab2_service.load_uber_reviews(limit=1, min_score=None, max_score=None)
    assert len(limited_rows) == 1


def test_parse_llm_json_plain() -> None:
    parsed = lab2_service.parse_llm_json('{"results":[{"row_id":1,"sentiment":"positive","issue_type":"ok","topic":"general","urgency":"low","summary":"ok","suggested_action":"ok"}]}')
    assert isinstance(parsed, dict)
    assert "results" in parsed


def test_parse_llm_json_fenced() -> None:
    raw = """```json
{"results":[{"row_id":1,"sentiment":"positive","issue_type":"ok","topic":"general","urgency":"low","summary":"ok","suggested_action":"ok"}]}
```"""
    parsed = lab2_service.parse_llm_json(raw)
    assert isinstance(parsed, dict)
    assert "results" in parsed


def _valid_results(ids: list[int]) -> dict:
    return {
        "results": [
            {
                "row_id": row_id,
                "sentiment": "positive",
                "issue_type": "service_quality",
                "topic": "ride_experience",
                "urgency": "low",
                "summary": "Положительный отзыв",
                "suggested_action": "Сохранить текущий уровень сервиса",
            }
            for row_id in ids
        ]
    }


def test_validate_result_success() -> None:
    data = _valid_results([1, 2])
    validated = lab2_service.validate_result(data, expected_row_ids={1, 2})
    assert len(validated) == 2
    assert all(isinstance(item, ReviewClassification) for item in validated)


def test_validate_result_missing_results() -> None:
    with pytest.raises(lab2_service.Lab2PipelineError):
        lab2_service.validate_result({"items": []}, expected_row_ids={1})


def test_validate_result_extra_row_id() -> None:
    data = _valid_results([1, 2, 3])
    with pytest.raises(lab2_service.Lab2PipelineError):
        lab2_service.validate_result(data, expected_row_ids={1, 2})


def test_validate_result_missing_row_id() -> None:
    data = _valid_results([1])
    with pytest.raises(lab2_service.Lab2PipelineError):
        lab2_service.validate_result(data, expected_row_ids={1, 2})


def test_batching_logic() -> None:
    reviews = [
        lab2_service.UberReviewInput(row_id=i, content=f"r{i}", score=5, thumbs_up_count=0, review_created_version=None, at=None, app_version=None)
        for i in range(1, 13)
    ]
    chunks = lab2_service._chunk_reviews(reviews, batch_size=5)
    assert len(chunks) == 3
    assert [len(chunk) for chunk in chunks] == [5, 5, 2]

    chunks2 = lab2_service._chunk_reviews(reviews[:3], batch_size=10)
    assert len(chunks2) == 1
    assert len(chunks2[0]) == 3


def test_lab2_status_endpoint(temp_paths: dict[str, Path]) -> None:
    _write_dataset(temp_paths["datasets_dir"] / "customer_reviews.csv")
    client = TestClient(app)
    response = client.get("/api/lab2/status")
    assert response.status_code == 200
    assert response.json()["lab"] == 2


def test_lab2_sample_data_endpoint(temp_paths: dict[str, Path]) -> None:
    _write_dataset(temp_paths["datasets_dir"] / "customer_reviews.csv")
    client = TestClient(app)
    response = client.get("/api/lab2/sample-data?limit=5")
    assert response.status_code == 200
    assert "sample" in response.json()


@pytest.mark.asyncio
async def test_lab2_run_with_mocked_ollama(temp_paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _write_dataset(temp_paths["datasets_dir"] / "customer_reviews.csv")

    async def fake_generate_json(self, model: str, prompt: str) -> OllamaGenerateResponse:  # noqa: ARG001
        marker = "Данные:\n"
        start = prompt.index(marker) + len(marker)
        reviews = json.loads(prompt[start:])
        results = _valid_results([item["row_id"] for item in reviews])
        return OllamaGenerateResponse(model=model, response=json.dumps(results, ensure_ascii=False), done=True, raw={})

    monkeypatch.setattr(lab2_service.OllamaClient, "generate_json", fake_generate_json)

    request = lab2_service.Lab2RunRequest(limit=5, batch_size=2, min_score=None, max_score=None)
    response = await lab2_service.run_pipeline(request)
    assert response.rows_processed > 0
    assert response.batches_processed >= 1

    output_path = temp_paths["outputs_dir"] / "lab2_result.json"
    assert output_path.exists()
    loaded = json.loads(output_path.read_text(encoding="utf-8"))
    assert "results" in loaded


def test_validate_result_error_object() -> None:
    with pytest.raises(lab2_service.Lab2PipelineError) as exc:
        lab2_service.validate_result({"error": "bad request"}, expected_row_ids={1})
    assert "LLM returned an error object instead of classification results" in str(exc.value)
