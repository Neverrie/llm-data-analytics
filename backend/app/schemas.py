from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


class Lab1StatusResponse(BaseModel):
    lab: int
    name: str
    status: str
    planned_features: list[str]


class Lab2SampleResult(BaseModel):
    dataset: str
    rows: int
    columns: int
    summary: str


class Lab2DemoResponse(BaseModel):
    lab: int
    name: str
    status: str
    pipeline: list[str]
    sample_result: Lab2SampleResult


class Lab3Architecture(BaseModel):
    planner: str
    tool_caller: str
    critic: str
    tools: list[str]


class Lab3StatusResponse(BaseModel):
    lab: int
    name: str
    status: str
    agent_architecture: Lab3Architecture
    security: list[str]


class OllamaChatMessage(BaseModel):
    role: str
    content: str


class OllamaChatResponse(BaseModel):
    model: str
    message: OllamaChatMessage
    done: bool
    raw: dict[str, Any]

