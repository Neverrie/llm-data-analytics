from app.schemas import Lab3Architecture, Lab3StatusResponse


def get_lab3_status() -> Lab3StatusResponse:
    return Lab3StatusResponse(
        lab=3,
        name="LLM Analytics Agent",
        status="skeleton-ready",
        agent_architecture=Lab3Architecture(
            planner="Qwen local model",
            tool_caller="Qwen Coder local model",
            critic="Reasoning model",
            tools=[
                "get_dataset_schema",
                "describe_numeric_columns",
                "detect_outliers",
                "correlation_analysis",
                "groupby_analysis",
                "create_chart"
            ]
        ),
        security=[
            "CSV content is treated as data, not instructions",
            "Only allowlisted tools can be called",
            "No arbitrary code execution from LLM output",
            "Tool arguments will be validated"
        ]
    )

