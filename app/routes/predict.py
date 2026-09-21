"""Prediction endpoint."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.inference.predictor import PredictorNotReady
from app.schemas.prediction import PredictionRequest, PredictionResponse

router = APIRouter(tags=["prediction"])


@router.post(
    "/predict",
    response_model=PredictionResponse,
    status_code=status.HTTP_200_OK,
)
def predict(payload: PredictionRequest, request: Request) -> PredictionResponse:
    predictor: Any = getattr(request.app.state, "predictor", None)
    if predictor is None or not predictor.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="production model is not ready",
        )

    started = time.perf_counter()
    try:
        result = predictor.predict(payload.text)
    except PredictorNotReady as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="production model is not ready",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="inference failed",
        ) from exc

    latency_ms = (time.perf_counter() - started) * 1000
    return PredictionResponse(
        prediction=result.prediction,
        confidence=result.confidence,
        model_version=result.model_version,
        latency_ms=latency_ms,
        request_id=request.state.request_id,
    )
