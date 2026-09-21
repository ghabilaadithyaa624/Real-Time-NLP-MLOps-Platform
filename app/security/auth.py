"""Optional bearer-token authentication without credential telemetry."""

from __future__ import annotations

import hmac
import os

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

_PUBLIC_PATHS = frozenset({"/health", "/health/ready"})


def _auth_mode() -> str:
    return os.getenv("API_AUTH_MODE", "disabled").strip().lower()


class BearerAuthenticationMiddleware(BaseHTTPMiddleware):
    """Protect application routes when explicitly enabled.

    External OIDC or API-gateway authentication remains preferred for
    production. This middleware is intended for controlled local or internal
    deployments that need a simple application-level gate.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        mode = _auth_mode()
        if mode == "disabled":
            return await call_next(request)
        if mode != "bearer":
            return JSONResponse(
                status_code=503,
                content={"detail": "authentication is misconfigured"},
            )

        expected_token = os.getenv("API_AUTH_TOKEN", "")
        if not expected_token:
            return JSONResponse(
                status_code=503,
                content={"detail": "authentication is not configured"},
            )

        authorization = request.headers.get("authorization", "")
        scheme, _, presented_token = authorization.partition(" ")
        valid = (
            scheme.lower() == "bearer"
            and bool(presented_token)
            and hmac.compare_digest(presented_token, expected_token)
        )
        if not valid:
            return JSONResponse(
                status_code=401,
                content={"detail": "authentication required"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)
