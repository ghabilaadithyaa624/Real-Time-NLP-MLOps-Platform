"""JSON structured logging with an explicit, safe field allow-list."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Mapping

SERVICE_NAME = "real-time-nlp-api"
_ALLOWED_EXTRA_FIELDS = frozenset(
    {
        "event",
        "request_id",
        "endpoint",
        "status_code",
        "latency_ms",
        "model_version",
        "model_source",
        "error_type",
    }
)


class JsonFormatter(logging.Formatter):
    """Render stable JSON records without copying arbitrary log extras."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "service": SERVICE_NAME,
            "message": record.getMessage(),
        }
        for field_name in _ALLOWED_EXTRA_FIELDS:
            if hasattr(record, field_name):
                value = getattr(record, field_name)
                if value is not None:
                    payload[field_name] = value
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging() -> logging.Logger:
    """Configure the application logger once and return it."""

    logger = logging.getLogger(SERVICE_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    return logger


def log_request_complete(
    logger: logging.Logger,
    *,
    request_id: str,
    endpoint: str,
    status_code: int,
    latency_ms: float,
    model_version: str,
) -> None:
    """Log request metadata only; raw request bodies are never accepted."""

    logger.info(
        "request.complete",
        extra={
            "event": "request.complete",
            "request_id": request_id,
            "endpoint": endpoint,
            "status_code": status_code,
            "latency_ms": round(latency_ms, 3),
            "model_version": model_version,
        },
    )


def log_model_event(
    logger: logging.Logger,
    message: str,
    *,
    event: str,
    model_source: str,
    model_version: str = "unknown",
    error_type: str | None = None,
) -> None:
    extra: dict[str, Any] = {
        "event": event,
        "model_source": model_source,
        "model_version": model_version,
    }
    if error_type:
        extra["error_type"] = error_type
    logger.info(message, extra=extra) if event.endswith("success") else logger.error(
        message, extra=extra
    )
