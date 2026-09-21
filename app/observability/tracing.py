"""Privacy-conscious OpenTelemetry tracing for the serving API."""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, Status, StatusCode, Tracer

SERVICE_NAME = "real-time-nlp-api"
SERVICE_VERSION = "0.1.0"

# Only these application-defined attributes may be added to custom spans. The
# FastAPI instrumentor supplies standard HTTP route/status attributes; it is
# explicitly configured not to capture request or response headers.
TRACE_ATTRIBUTE_ALLOWLIST = frozenset(
    {
        "nlp.model.source",
        "nlp.model.version",
        "nlp.model.load.outcome",
        "nlp.inference.device",
        "error.type",
    }
)

_provider: TracerProvider | None = None


def tracing_enabled() -> bool:
    """Return whether OTLP export was explicitly enabled by configuration."""

    if os.getenv("OTEL_SDK_DISABLED", "false").strip().lower() == "true":
        return False
    exporter = os.getenv("OTEL_TRACES_EXPORTER", "none").strip().lower()
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT", ""
    )
    return exporter == "otlp" and bool(endpoint.strip())


def _resource() -> Resource:
    service_name = os.getenv("OTEL_SERVICE_NAME", SERVICE_NAME).strip() or SERVICE_NAME
    return Resource.create(
        {
            "service.name": service_name,
            "service.version": SERVICE_VERSION,
            "deployment.environment": os.getenv(
                "OTEL_DEPLOYMENT_ENVIRONMENT", "local"
            ),
        }
    )


def configure_tracing(
    *,
    tracer_provider: TracerProvider | None = None,
) -> TracerProvider | None:
    """Configure one process-wide OTLP provider, or leave tracing as no-op.

    Supplying a provider is supported for deterministic tests. In normal
    serving, OTLP export is opt-in so the API does not retry against a missing
    collector when it is run without the observability profile.
    """

    global _provider

    if tracer_provider is not None:
        return tracer_provider
    if _provider is not None:
        return _provider
    if not tracing_enabled():
        return None

    exporter_name = os.getenv("OTEL_TRACES_EXPORTER", "none").strip().lower()
    if exporter_name != "otlp":
        raise ValueError("only the OTLP trace exporter is supported")
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT", ""
    )
    if not endpoint.strip():
        raise ValueError("OTLP tracing requires an exporter endpoint")

    provider = TracerProvider(resource=_resource())
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=endpoint.strip(),
                insecure=endpoint.strip().startswith("http://"),
            )
        )
    )
    # OpenTelemetry intentionally permits setting the global provider once.
    # Keeping the reference also lets the application expose the provider to
    # manual spans without repeatedly attempting global configuration.
    trace.set_tracer_provider(provider)
    _provider = provider
    return provider


def get_tracer(tracer_provider: TracerProvider | None = None) -> Tracer:
    """Return the application tracer for automatic or manual spans."""

    return trace.get_tracer(
        SERVICE_NAME,
        SERVICE_VERSION,
        tracer_provider=tracer_provider,
    )


def set_safe_span_attributes(span: Span, **attributes: Any) -> None:
    """Apply only bounded, non-customer fields to an application span."""

    if not span.is_recording():
        return
    for key, value in attributes.items():
        if key not in TRACE_ATTRIBUTE_ALLOWLIST:
            continue
        if isinstance(value, (str, bool, int, float)):
            span.set_attribute(key, value)


def mark_span_error(span: Span, exception: BaseException) -> None:
    """Mark failure without recording exception text or customer data."""

    if not span.is_recording():
        return
    span.set_status(Status(StatusCode.ERROR))
    set_safe_span_attributes(span, **{"error.type": type(exception).__name__})


def instrument_fastapi(
    app: FastAPI,
    *,
    tracer_provider: TracerProvider | None = None,
) -> None:
    """Add FastAPI spans while disabling header capture and body collection."""

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=tracer_provider,
        # Empty lists intentionally override environment-based header capture.
        http_capture_headers_server_request=[],
        http_capture_headers_server_response=[],
        http_capture_headers_sanitize_fields=[
            "authorization",
            "cookie",
            "set-cookie",
            "x-api-key",
        ],
    )
