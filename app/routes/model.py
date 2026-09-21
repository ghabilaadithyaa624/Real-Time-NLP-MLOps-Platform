"""Model metadata endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas.health import ModelResponse

router = APIRouter(tags=["model"])


@router.get("/model", response_model=ModelResponse)
def model_info(request: Request) -> ModelResponse:
    predictor = getattr(request.app.state, "predictor", None)
    if predictor is None or not predictor.is_ready:
        return ModelResponse(
            status="not_ready",
            model_source="unknown",
            model_version=None,
            device=None,
        )
    device = getattr(predictor, "device", None)
    return ModelResponse(
        status="ready",
        model_source=str(getattr(predictor, "model_source", "unknown")),
        model_version=str(getattr(predictor, "model_version", "unknown")),
        device=str(device) if device is not None else None,
    )
