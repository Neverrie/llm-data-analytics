from app.schemas import Lab1StatusResponse


def get_lab1_status() -> Lab1StatusResponse:
    return Lab1StatusResponse(
        lab=1,
        name="Prompt Engineering EDA",
        status="skeleton-ready",
        planned_features=[
            "CSV upload",
            "4 prompt blocks",
            "LLM responses",
            "student comments",
            "Markdown/PDF export"
        ]
    )

