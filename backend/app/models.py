from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ProfileResponse(BaseModel):
    dataset_id: str
    name: str
    profile: dict[str, Any]
    suggestions: list[dict[str, str]]


class ChatRequest(BaseModel):
    session_id: str
    dataset_id: str
    message: str


class ExecutionStep(BaseModel):
    label: str
    detail: str
    status: str  # "ok" | "retried" | "error"


class ChatResponse(BaseModel):
    answer: str
    sql: str | None = None
    chart: dict[str, Any] | None = None
    facts: dict[str, Any] | None = None
    execution_trace: list[ExecutionStep] = []
    execution_ms: float | None = None
    low_confidence: bool = False
    error: str | None = None
