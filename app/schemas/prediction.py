"""Prediction request and response contracts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1, max_length=10_000)

    @field_validator("text")
    @classmethod
    def text_must_contain_non_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must contain non-whitespace characters")
        return value


class PredictionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prediction: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    model_version: str
    latency_ms: float = Field(..., ge=0.0)
    request_id: str
