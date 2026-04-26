from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.config import settings
from app.services import lab3_column_mapper
from app.services.lab2_service import Lab2PipelineError


@pytest.fixture
def mapper_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    datasets_dir = tmp_path / "datasets"
    datasets_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "datasets_dir", str(datasets_dir))
    monkeypatch.setattr(settings, "lab2_dataset_filename", "customer_reviews")
    return datasets_dir


def _write_uber_dataset(path: Path) -> None:
    frame = pd.DataFrame(
        [
            {
                "userName": "u1",
                "userImage": "img.png",
                "content": "Driver was late and payment failed",
                "score": 1,
                "thumbsUpCount": 2,
                "reviewCreatedVersion": "4.556.10005",
                "at": "2024-12-18 17:17:19",
                "replyContent": "We are sorry",
                "repliedAt": "2024-12-19 10:00:00",
                "appVersion": "4.556.10005",
            },
            {
                "userName": "u2",
                "userImage": "img2.png",
                "content": "Great app",
                "score": 5,
                "thumbsUpCount": 1,
                "reviewCreatedVersion": "4.556.10005",
                "at": "2024-12-19 12:00:00",
                "replyContent": None,
                "repliedAt": None,
                "appVersion": "4.556.10005",
            },
        ]
    )
    frame.to_csv(path, index=False)


def test_profile_dataset(mapper_paths: Path) -> None:
    _write_uber_dataset(mapper_paths / "customers_reviews.csv")
    profile = lab3_column_mapper.profile_dataset("customers_reviews.csv")
    assert profile["total_rows"] == 2
    assert "content" in profile["columns"]
    assert "score" in profile["dtypes"]


def test_infer_uber_column_roles(mapper_paths: Path) -> None:
    _write_uber_dataset(mapper_paths / "customers_reviews.csv")
    profile = lab3_column_mapper.profile_dataset("customers_reviews.csv")
    mapping = lab3_column_mapper.infer_column_roles_heuristic(profile)
    assert mapping.roles["text_column"].column == "content"
    assert mapping.roles["rating_column"].column == "score"
    assert mapping.roles["date_column"].column == "at"
    assert mapping.roles["version_column"].column == "appVersion"
    assert mapping.roles["reply_column"].column == "replyContent"
    assert mapping.roles["reply_date_column"].column == "repliedAt"


@pytest.mark.asyncio
async def test_user_overrides(mapper_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_uber_dataset(mapper_paths / "customers_reviews.csv")

    async def fake_llm(profile, heuristic):  # noqa: ANN001
        return heuristic

    monkeypatch.setattr(lab3_column_mapper, "infer_column_roles_llm", fake_llm)
    _, mapping = await lab3_column_mapper.get_effective_column_mapping(
        "customers_reviews.csv",
        user_overrides={"text_column": "content", "rating_column": "score"},
    )
    assert mapping.roles["text_column"].column == "content"
    assert mapping.roles["rating_column"].column == "score"


@pytest.mark.asyncio
async def test_invalid_user_override(mapper_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_uber_dataset(mapper_paths / "customers_reviews.csv")

    async def fake_llm(profile, heuristic):  # noqa: ANN001
        return heuristic

    monkeypatch.setattr(lab3_column_mapper, "infer_column_roles_llm", fake_llm)
    with pytest.raises(Lab2PipelineError):
        await lab3_column_mapper.get_effective_column_mapping(
            "customers_reviews.csv",
            user_overrides={"text_column": "missing_column"},
        )
