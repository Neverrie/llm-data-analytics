from typing import Any


def is_analytical_request(text: str) -> bool:
    normalized = (text or "").lower()
    keywords = (
        "анализ",
        "проанализ",
        "граф",
        "chart",
        "plot",
        "dataset",
        "датасет",
        "таблиц",
        "сводк",
        "статист",
        "csv",
    )
    return any(keyword in normalized for keyword in keywords)


def required_file_extensions(text: str) -> set[str]:
    normalized = (text or "").lower()
    required: set[str] = set()
    groups = {
        ".md": (".md", "markdown", "маркдаун", "md файл", "md-файл"),
        ".csv": (".csv", "csv файл", "csv-файл"),
        ".xlsx": (".xlsx", "excel", "эксель"),
        ".json": (".json", "json файл", "json-файл"),
    }
    for extension, tokens in groups.items():
        if any(token in normalized for token in tokens):
            required.add(extension)
    return required


def missing_file_extensions(files: dict[str, dict[str, Any]], required: set[str]) -> set[str]:
    present: set[str] = set()
    for item in files.values():
        filename = str(item.get("filename") or "").lower()
        if "." in filename:
            present.add("." + filename.rsplit(".", 1)[-1])
    return required - present
