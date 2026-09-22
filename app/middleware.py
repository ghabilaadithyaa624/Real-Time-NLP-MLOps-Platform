"""HTTP middleware for correlation and response security policy."""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.monitoring.metrics import record_http_request, route_template
from app.observability.logging import log_request_complete


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a correlation ID to every request and response."""

    def __init__(self, app: Any, logger: Any) -> None:
        super().__init__(app)
        self.logger = logger

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
            elapsed_seconds = time.perf_counter() - started
            endpoint = route_template(request.scope)
            record_http_request(request.method, endpoint, 500, elapsed_seconds)
            log_request_complete(
                self.logger,
                request_id=request_id,
                endpoint=endpoint,
                status_code=500,
                latency_ms=elapsed_seconds * 1000,
                model_version=str(
                    getattr(
                        getattr(request.app.state, "predictor", None),
                        "model_version",
                        "unknown",
                    )
                ),
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
            self.logger,
            request_id=request_id,
            endpoint=endpoint,
            status_code=response.status_code,
            latency_ms=elapsed_seconds * 1000,
            model_version=str(
                getattr(
                    getattr(request.app.state, "predictor", None),
                    "model_version",
                    "unknown",
                )
            ),
        )
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add conservative headers suitable for a JSON-only API."""

    _HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        "Cache-Control": "no-store",
    }

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)
        for name, value in self._HEADERS.items():
            response.headers.setdefault(name, value)
        if os.getenv("ENABLE_HSTS", "false").strip().lower() == "true":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response
