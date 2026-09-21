"""Health and model metadata response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    service: str


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    service: str
    model_loaded: bool
    reason: str | None = None


class ModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    model_source: str
    model_version: str | None = None
    device: str | None = None
