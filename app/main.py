"""FastAPI application entry point."""

from __future__ import annotations

import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.inference.predictor import PredictorNotReady, TransformerPredictor
from app.monitoring.metrics import (
    record_http_request,
    record_model_loading_error,
    route_template,
)
from app.observability.logging import (
    configure_logging,
    log_model_event,
    log_request_complete,
)
from app.routes.health import router as health_router
from app.routes.metrics import router as metrics_router
from app.routes.model import router as model_router
from app.routes.predict import router as predict_router

logger = configure_logging()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a correlation ID to every request and response."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            record_http_request(
                request.method,
                route_template(request.scope),
                500,
                time.perf_counter() - started,
            )
            raise
        elapsed_seconds = time.perf_counter() - started
        endpoint = route_template(request.scope)
        record_http_request(
            request.method,
            endpoint,
            response.status_code,
            elapsed_seconds,
        )
        log_request_complete(
            logger,
            request_id=request_id,
            endpoint=endpoint,
            status_code=response.status_code,
            latency_ms=elapsed_seconds * 1000,
            model_version=str(
                getattr(getattr(request.app.state, "predictor", None), "model_version", "unknown")
            ),
        )
        response.headers["X-Request-ID"] = request_id
        return response


def create_app(predictor: Any | None = None) -> FastAPI:
    """Create the API application with optional dependency injection for tests."""

    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if predictor is not None:
            app.state.predictor = predictor
        else:
            try:
                loaded_predictor = TransformerPredictor.from_environment()
                loaded_predictor.warmup()
                app.state.predictor = loaded_predictor
                log_model_event(
                    logger,
                    "model.load.success",
                    event="model.load.success",
                    model_source=str(getattr(loaded_predictor, "model_source", "unknown")),
                    model_version=str(getattr(loaded_predictor, "model_version", "unknown")),
                )
            except (PredictorNotReady, ValueError, OSError) as exc:
                # Keep liveness available while readiness remains false. This
                # lets Kubernetes replace/retry an unready pod explicitly.
                app.state.predictor = None
                app.state.model_load_error = str(exc)
                model_source = os.getenv("MODEL_SOURCE", "mlflow")
                record_model_loading_error(model_source)
                log_model_event(
                    logger,
                    "model.load.failure",
                    event="model.load.failure",
                    model_source=model_source,
                    error_type=type(exc).__name__,
                )
        yield

    app = FastAPI(
        title="Customer Feedback Intelligence API",
        version="0.1.0",
        description="Real-time Transformer sentiment inference API",
        lifespan=lifespan,
    )
    app.add_middleware(RequestIDMiddleware)
    app.include_router(health_router)
    app.include_router(model_router)
    app.include_router(predict_router)
    app.include_router(metrics_router)
    return app


app = create_app()
