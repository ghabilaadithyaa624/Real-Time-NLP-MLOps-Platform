from dataclasses import dataclass
from unittest.mock import Mock

from fastapi.testclient import TestClient
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from app.inference.predictor import PredictionResult, PredictorNotReady
from app.main import create_app
from app.observability.tracing import (
    SERVICE_NAME,
    set_safe_span_attributes,
    tracing_enabled,
)


@dataclass
class FakePredictor:
    model_version: str = "production"
    model_source: str = "test"
    device: str = "cpu"
    is_ready: bool = True

    def warmup(self) -> None:
        return None

    def predict(self, text: str) -> PredictionResult:
        assert text
        return PredictionResult(
            prediction="positive",
            confidence=0.98,
            model_version=self.model_version,
        )


def _provider_and_exporter() -> tuple[TracerProvider, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider(
        resource=Resource.create({"service.name": SERVICE_NAME})
    )
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def test_tracing_is_opt_in(monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)

    assert tracing_enabled() is False


def test_custom_trace_attributes_use_an_allow_list():
    provider, exporter = _provider_and_exporter()
    tracer = provider.get_tracer(SERVICE_NAME)

    with tracer.start_as_current_span("test") as span:
        set_safe_span_attributes(
            span,
            **{
                "nlp.model.version": "v1",
                "customer.text": "must not be stored",
            },
        )

    attributes = dict(exporter.get_finished_spans()[0].attributes)
    assert attributes == {"nlp.model.version": "v1"}


def test_http_and_inference_spans_exclude_body_and_authorization():
    provider, exporter = _provider_and_exporter()

    with TestClient(create_app(FakePredictor(), tracer_provider=provider)) as client:
        response = client.post(
            "/predict",
            json={"text": "private customer feedback"},
            headers={
                "Authorization": "Bearer secret-token",
                "X-Request-ID": "request-test-123",
            },
        )

    assert response.status_code == 200
    spans = exporter.get_finished_spans()
    names = {span.name for span in spans}
    assert "nlp.inference" in names
    assert any(dict(span.attributes).get("http.route") == "/predict" for span in spans)

    serialized = repr([(span.name, dict(span.attributes)) for span in spans])
    assert "private customer feedback" not in serialized
    assert "secret-token" not in serialized
    assert "request-test-123" not in serialized

    inference = next(span for span in spans if span.name == "nlp.inference")
    assert dict(inference.attributes)["nlp.model.version"] == "production"
    assert dict(inference.attributes)["nlp.model.source"] == "test"


def test_model_load_success_span_contains_safe_metadata(monkeypatch):
    provider, exporter = _provider_and_exporter()
    monkeypatch.setattr(
        "app.main.TransformerPredictor.from_environment",
        Mock(return_value=FakePredictor(model_version="candidate-7")),
    )

    with TestClient(create_app(tracer_provider=provider)) as client:
        assert client.get("/health/ready").status_code == 200

    load_span = next(
        span for span in exporter.get_finished_spans() if span.name == "model.load"
    )
    attributes = dict(load_span.attributes)
    assert attributes["nlp.model.source"] == "test"
    assert attributes["nlp.model.version"] == "candidate-7"
    assert attributes["nlp.model.load.outcome"] == "success"


def test_model_load_failure_span_contains_type_but_not_exception_text(monkeypatch):
    provider, exporter = _provider_and_exporter()
    monkeypatch.setattr(
        "app.main.TransformerPredictor.from_environment",
        Mock(side_effect=PredictorNotReady("private registry details")),
    )

    with TestClient(create_app(tracer_provider=provider)) as client:
        assert client.get("/health").status_code == 200

    load_span = next(
        span for span in exporter.get_finished_spans() if span.name == "model.load"
    )
    attributes = dict(load_span.attributes)
    assert load_span.status.status_code == StatusCode.ERROR
    assert attributes["error.type"] == "PredictorNotReady"
    assert attributes["nlp.model.load.outcome"] == "failure"
    assert "private registry details" not in repr(attributes)
