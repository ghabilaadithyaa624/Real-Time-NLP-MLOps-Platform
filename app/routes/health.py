"""Liveness and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])
SERVICE_NAME = "real-time-nlp-api"


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME)


@router.get("/health/ready", response_model=ReadinessResponse)
def readiness(request: Request) -> ReadinessResponse:
    predictor = getattr(request.app.state, "predictor", None)
    ready = predictor is not None and predictor.is_ready
    response = ReadinessResponse(
        status="ready" if ready else "not_ready",
        service=SERVICE_NAME,
        model_loaded=ready,
        reason=None if ready else "model is not loaded",
    )
    if not ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response.model_dump(),
        )
    return response
