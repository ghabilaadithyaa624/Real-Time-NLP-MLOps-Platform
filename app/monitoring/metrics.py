"""Prometheus metrics with bounded label cardinality."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest

REGISTRY = CollectorRegistry(auto_describe=True)

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests handled by the API",
    ("method", "route", "status_class"),
    registry=REGISTRY,
)
HTTP_REQUEST_LATENCY = Histogram(
    "http_request_latency_seconds",
    "HTTP request latency in seconds",
    ("method", "route"),
    registry=REGISTRY,
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
NLP_PREDICTIONS = Counter(
    "nlp_predictions_total",
    "Successful NLP predictions",
    ("prediction", "model_version"),
    registry=REGISTRY,
)
NLP_PREDICTION_ERRORS = Counter(
    "nlp_prediction_errors_total",
    "Prediction failures",
    ("error_type", "model_version"),
    registry=REGISTRY,
)
NLP_PREDICTION_LATENCY = Histogram(
    "nlp_prediction_latency_seconds",
    "NLP inference latency in seconds",
    ("model_version",),
    registry=REGISTRY,
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)
NLP_PREDICTION_CONFIDENCE = Histogram(
    "nlp_prediction_confidence",
    "Confidence of successful NLP predictions",
    ("model_version",),
    registry=REGISTRY,
    buckets=(0.0, 0.5, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0),
)
MODEL_LOADING_ERRORS = Counter(
    "model_loading_errors_total",
    "Model loading failures",
    ("model_source",),
    registry=REGISTRY,
)

_ALLOWED_ROUTES = frozenset({"/health", "/health/ready", "/model", "/predict", "/metrics"})


def route_template(scope: dict) -> str:
    """Return a bounded route label, never an arbitrary request path."""

    route = scope.get("route")
    template = getattr(route, "path", None)
    return template if template in _ALLOWED_ROUTES else "other"


def status_class(status_code: int) -> str:
    """Map status codes to a bounded class label."""

    return f"{status_code // 100}xx" if 100 <= status_code <= 599 else "unknown"


def record_http_request(method: str, route: str, status_code: int, elapsed_seconds: float) -> None:
    route = route if route in _ALLOWED_ROUTES else "other"
    HTTP_REQUESTS.labels(method=method, route=route, status_class=status_class(status_code)).inc()
    HTTP_REQUEST_LATENCY.labels(method=method, route=route).observe(elapsed_seconds)


def record_prediction_success(prediction: str, model_version: str) -> None:
    NLP_PREDICTIONS.labels(
        prediction=str(prediction),
        model_version=str(model_version),
    ).inc()


def record_prediction_error(error_type: str, model_version: str) -> None:
    bounded_error_type = error_type if error_type in {"not_ready", "inference"} else "other"
    NLP_PREDICTION_ERRORS.labels(
        error_type=bounded_error_type,
        model_version=str(model_version),
    ).inc()


def record_prediction_latency(model_version: str, elapsed_seconds: float) -> None:
    NLP_PREDICTION_LATENCY.labels(model_version=str(model_version)).observe(
        elapsed_seconds
    )


def record_prediction_confidence(model_version: str, confidence: float) -> None:
    bounded_confidence = min(max(float(confidence), 0.0), 1.0)
    NLP_PREDICTION_CONFIDENCE.labels(model_version=str(model_version)).observe(
        bounded_confidence
    )


def record_model_loading_error(model_source: str) -> None:
    bounded_source = model_source if model_source in {"local", "mlflow"} else "other"
    MODEL_LOADING_ERRORS.labels(model_source=bounded_source).inc()


def render_metrics() -> bytes:
    return generate_latest(REGISTRY)


__all__ = [
    "CONTENT_TYPE_LATEST",
    "MODEL_LOADING_ERRORS",
    "NLP_PREDICTION_ERRORS",
    "NLP_PREDICTION_LATENCY",
    "NLP_PREDICTION_CONFIDENCE",
    "NLP_PREDICTIONS",
    "REGISTRY",
    "HTTP_REQUESTS",
    "HTTP_REQUEST_LATENCY",
    "record_http_request",
    "record_model_loading_error",
    "record_prediction_error",
    "record_prediction_latency",
    "record_prediction_confidence",
    "record_prediction_success",
    "render_metrics",
    "route_template",
]
