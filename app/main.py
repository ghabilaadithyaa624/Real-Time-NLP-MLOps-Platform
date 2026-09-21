"""FastAPI application entry point."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI

from app.inference.predictor import PredictorNotReady, TransformerPredictor
from app.middleware import RequestIDMiddleware, SecurityHeadersMiddleware
from app.monitoring.metrics import record_model_loading_error
from app.observability.logging import configure_logging, log_model_event
from app.observability.tracing import (
    configure_tracing,
    get_tracer,
    instrument_fastapi,
    mark_span_error,
    set_safe_span_attributes,
)
from app.security.auth import BearerAuthenticationMiddleware
from app.routes.health import router as health_router
from app.routes.metrics import router as metrics_router
from app.routes.model import router as model_router
from app.routes.predict import router as predict_router

logger = configure_logging()


def create_app(
    predictor: Any | None = None,
    tracer_provider: Any | None = None,
) -> FastAPI:
    """Create the API application with optional dependency injection for tests."""

    configure_logging()
    configured_tracer_provider = configure_tracing(tracer_provider=tracer_provider)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if predictor is not None:
            app.state.predictor = predictor
        else:
            tracer = get_tracer(app.state.tracer_provider)
            with tracer.start_as_current_span("model.load") as span:
                try:
                    loaded_predictor = TransformerPredictor.from_environment()
                    loaded_predictor.warmup()
                    app.state.predictor = loaded_predictor
                    set_safe_span_attributes(
                        span,
                        **{
                            "nlp.model.source": str(
                                getattr(loaded_predictor, "model_source", "unknown")
                            ),
                            "nlp.model.version": str(
                                getattr(loaded_predictor, "model_version", "unknown")
                            ),
                            "nlp.model.load.outcome": "success",
                        },
                    )
                    log_model_event(
                        logger,
                        "model.load.success",
                        event="model.load.success",
                        model_source=str(
                            getattr(loaded_predictor, "model_source", "unknown")
                        ),
                        model_version=str(
                            getattr(loaded_predictor, "model_version", "unknown")
                        ),
                    )
                except (PredictorNotReady, ValueError, OSError) as exc:
                    # Keep liveness available while readiness remains false. This
                    # lets Kubernetes replace/retry an unready pod explicitly.
                    app.state.predictor = None
                    app.state.model_load_error = str(exc)
                    model_source = os.getenv("MODEL_SOURCE", "mlflow")
                    record_model_loading_error(model_source)
                    mark_span_error(span, exc)
                    set_safe_span_attributes(
                        span,
                        **{
                            "nlp.model.source": model_source,
                            "nlp.model.load.outcome": "failure",
                        },
                    )
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
    app.state.tracer_provider = configured_tracer_provider
    instrument_fastapi(app, tracer_provider=configured_tracer_provider)
    app.add_middleware(BearerAuthenticationMiddleware)
    app.add_middleware(RequestIDMiddleware, logger=logger)
    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(health_router)
    app.include_router(model_router)
    app.include_router(predict_router)
    app.include_router(metrics_router)
    return app


app = create_app()
