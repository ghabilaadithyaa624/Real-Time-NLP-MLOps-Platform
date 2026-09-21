"""FastAPI application entry point."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.inference.predictor import PredictorNotReady, TransformerPredictor
from app.routes.health import router as health_router
from app.routes.model import router as model_router
from app.routes.predict import router as predict_router

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a correlation ID to every request and response."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def create_app(predictor: Any | None = None) -> FastAPI:
    """Create the API application with optional dependency injection for tests."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if predictor is not None:
            app.state.predictor = predictor
        else:
            try:
                app.state.predictor = TransformerPredictor.from_environment()
                logger.info("model loaded successfully")
            except (PredictorNotReady, ValueError, OSError) as exc:
                # Keep liveness available while readiness remains false. This
                # lets Kubernetes replace/retry an unready pod explicitly.
                app.state.predictor = None
                app.state.model_load_error = str(exc)
                logger.error("model load failed: %s", exc)
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
    return app


app = create_app()
