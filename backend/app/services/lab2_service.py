from app.schemas import Lab2DemoResponse, Lab2SampleResult


def get_lab2_demo() -> Lab2DemoResponse:
    return Lab2DemoResponse(
        lab=2,
        name="API Pipeline",
        status="demo",
        pipeline=[
            "read_csv",
            "build_prompt",
            "call_llm_api",
            "parse_json",
            "save_result"
        ],
        sample_result=Lab2SampleResult(
            dataset="demo.csv",
            rows=500,
            columns=8,
            summary="Demo pipeline response. Real LLM integration will be added later."
        )
    )

