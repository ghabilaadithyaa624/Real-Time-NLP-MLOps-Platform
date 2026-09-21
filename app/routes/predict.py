"""Prediction endpoint."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.inference.predictor import PredictorNotReady
from app.monitoring.metrics import (
    record_prediction_error,
    record_prediction_latency,
    record_prediction_success,
)
from app.schemas.prediction import PredictionRequest, PredictionResponse

router = APIRouter(tags=["prediction"])


@router.post(
    "/predict",
    response_model=PredictionResponse,
    status_code=status.HTTP_200_OK,
)
def predict(payload: PredictionRequest, request: Request) -> PredictionResponse:
    started = time.perf_counter()
    predictor: Any = getattr(request.app.state, "predictor", None)
    model_version = str(getattr(predictor, "model_version", "unknown"))
    if predictor is None or not predictor.is_ready:
        record_prediction_error("not_ready", model_version)
        record_prediction_latency(model_version, time.perf_counter() - started)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="production model is not ready",
        )

    try:
        result = predictor.predict(payload.text)
    except PredictorNotReady as exc:
        record_prediction_error("not_ready", model_version)
        record_prediction_latency(model_version, time.perf_counter() - started)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="production model is not ready",
        ) from exc
    except Exception as exc:
        record_prediction_error("inference", model_version)
        record_prediction_latency(model_version, time.perf_counter() - started)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="inference failed",
        ) from exc

    elapsed_seconds = time.perf_counter() - started
    record_prediction_success(result.prediction, result.model_version)
    record_prediction_latency(result.model_version, elapsed_seconds)
    return PredictionResponse(
        prediction=result.prediction,
        confidence=result.confidence,
        model_version=result.model_version,
        latency_ms=elapsed_seconds * 1000,
        request_id=request.state.request_id,
    )
