"""Prometheus metrics endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from starlette.responses import Response

from app.monitoring.metrics import CONTENT_TYPE_LATEST, render_metrics

router = APIRouter(tags=["monitoring"])


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=render_metrics(), media_type=CONTENT_TYPE_LATEST)
