from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.schemas import ReviewClassification
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
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_model", "openai/gpt-oss-120b:free")
    return {"datasets_dir": datasets_dir, "outputs_dir": outputs_dir}


def _write_dataset(path: Path) -> None:
    frame = pd.DataFrame(
        [
            {"content": " Good app ", "score": "5", "thumbsUpCount": "2", "reviewCreatedVersion": "1.0", "at": "2024-01-01", "appVersion": "1.0"},
            {"content": "   ", "score": "4.0", "thumbsUpCount": "", "reviewCreatedVersion": None, "at": None, "appVersion": None},
            {"content": "Bad support", "score": "not_a_number", "thumbsUpCount": "7", "reviewCreatedVersion": "1.2", "at": "2024-01-02", "appVersion": "1.2"},
            {"content": "Average", "score": 2, "thumbsUpCount": None, "reviewCreatedVersion": "1.3", "at": "2024-01-03", "appVersion": "1.3"},
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
    assert total_rows == 3
    assert len(rows) == 3


def test_parse_llm_json_plain() -> None:
    parsed = lab2_service.parse_llm_json('{"results":[{"row_id":1,"sentiment":"positive","issue_type":"ok","topic":"general","urgency":"low","summary":"ok","suggested_action":"ok"}]}')
    assert isinstance(parsed, dict)


def test_parse_llm_json_fenced() -> None:
    parsed = lab2_service.parse_llm_json("""```json
{"results":[{"row_id":1,"sentiment":"positive","issue_type":"ok","topic":"general","urgency":"low","summary":"ok","suggested_action":"ok"}]}
```""")
    assert isinstance(parsed, dict)


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
                "suggested_action": "Сохранить уровень сервиса",
            }
            for row_id in ids
        ]
    }


def test_validate_result_success() -> None:
    validated = lab2_service.validate_result(_valid_results([1, 2]), expected_row_ids={1, 2})
    assert len(validated) == 2
    assert all(isinstance(item, ReviewClassification) for item in validated)


def test_validate_result_missing_results() -> None:
    with pytest.raises(lab2_service.Lab2PipelineError):
        lab2_service.validate_result({"items": []}, expected_row_ids={1})


def test_validate_result_extra_row_id() -> None:
    with pytest.raises(lab2_service.Lab2PipelineError):
        lab2_service.validate_result(_valid_results([1, 2, 3]), expected_row_ids={1, 2})


def test_validate_result_missing_row_id() -> None:
    with pytest.raises(lab2_service.Lab2PipelineError):
        lab2_service.validate_result(_valid_results([1]), expected_row_ids={1, 2})


def test_batching_logic() -> None:
    reviews = [lab2_service.UberReviewInput(row_id=i, content=f"r{i}", score=5, thumbs_up_count=0) for i in range(1, 13)]
    chunks = lab2_service._chunk_reviews(reviews, batch_size=5)
    assert [len(chunk) for chunk in chunks] == [5, 5, 2]


def test_lab2_status_endpoint(temp_paths: dict[str, Path]) -> None:
    _write_dataset(temp_paths["datasets_dir"] / "customer_reviews.csv")
    client = TestClient(app)
    response = client.get("/api/lab2/status")
    assert response.status_code == 200
    assert response.json()["provider"] in {"openrouter", "ollama"}


def test_lab2_sample_data_endpoint(temp_paths: dict[str, Path]) -> None:
    _write_dataset(temp_paths["datasets_dir"] / "customer_reviews.csv")
    client = TestClient(app)
    response = client.get("/api/lab2/sample-data?limit=5")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_lab2_uses_unified_llm_client_mocked(temp_paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _write_dataset(temp_paths["datasets_dir"] / "customer_reviews.csv")
    called = {"value": False}

    async def fake_chat_json(self, messages, purpose="json", model=None, temperature=0.1):  # noqa: ANN001,ARG001
        called["value"] = True
        prompt = messages[-1]["content"]
        marker = "Данные:\n"
        start = prompt.index(marker) + len(marker)
        reviews = json.loads(prompt[start:])
        return _valid_results([item["row_id"] for item in reviews])

    monkeypatch.setattr(lab2_service.LLMClient, "chat_json", fake_chat_json)

    response = await lab2_service.run_pipeline(lab2_service.Lab2RunRequest(limit=5, batch_size=2, min_score=None, max_score=None))
    assert called["value"] is True
    assert response.rows_processed > 0


@pytest.mark.asyncio
async def test_lab2_batch_size_optional(temp_paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _write_dataset(temp_paths["datasets_dir"] / "customer_reviews.csv")

    async def fake_chat_json(self, messages, purpose="json", model=None, temperature=0.1):  # noqa: ANN001,ARG001
        prompt = messages[-1]["content"]
        marker = "Данные:\n"
        start = prompt.index(marker) + len(marker)
        reviews = json.loads(prompt[start:])
        return _valid_results([item["row_id"] for item in reviews])

    monkeypatch.setattr(lab2_service.LLMClient, "chat_json", fake_chat_json)
    response = await lab2_service.run_pipeline(lab2_service.Lab2RunRequest(limit=3, batch_size=None))
    assert response.batch_size == 3


@pytest.mark.asyncio
async def test_lab2_process_all_limited(temp_paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    frame = pd.DataFrame(
        [{"content": f"review {idx}", "score": 5, "thumbsUpCount": 0, "reviewCreatedVersion": "1.0", "at": "2024-01-01", "appVersion": "1.0"} for idx in range(1500)]
    )
    frame.to_csv(temp_paths["datasets_dir"] / "customer_reviews.csv", index=False)

    async def fake_chat_json(self, messages, purpose="json", model=None, temperature=0.1):  # noqa: ANN001,ARG001
        prompt = messages[-1]["content"]
        marker = "Данные:\n"
        start = prompt.index(marker) + len(marker)
        reviews = json.loads(prompt[start:])
        return _valid_results([item["row_id"] for item in reviews])

    monkeypatch.setattr(lab2_service.LLMClient, "chat_json", fake_chat_json)
    response = await lab2_service.run_pipeline(lab2_service.Lab2RunRequest(process_all=True))
    assert response.rows_processed == lab2_service.MAX_PROCESS_ALL_ROWS
    assert any("первые" in warning.lower() for warning in response.warnings)


def test_validate_result_error_object() -> None:
    with pytest.raises(lab2_service.Lab2PipelineError):
        lab2_service.validate_result({"error": "bad request"}, expected_row_ids={1})
