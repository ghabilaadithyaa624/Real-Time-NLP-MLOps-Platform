from fastapi.testclient import TestClient

from app.main import create_app
from app.monitoring.metrics import (
    record_model_loading_error,
    record_prediction_error,
    record_prediction_latency,
    record_prediction_success,
)
from app.inference.predictor import PredictionResult


class MetricsPredictor:
    is_ready = True
    model_version = "metrics-test"
    model_source = "test"
    device = "cpu"

    def predict(self, text: str) -> PredictionResult:
        return PredictionResult(
            prediction="positive",
            confidence=0.9,
            model_version=self.model_version,
        )


def test_prediction_and_http_metrics_are_exposed_without_high_cardinality_data():
    record_prediction_success("positive", "metrics-test")
    record_prediction_error("inference", "metrics-test")
    record_prediction_latency("metrics-test", 0.01)
    record_model_loading_error("mlflow")

    with TestClient(create_app(MetricsPredictor())) as client:
        response = client.post(
            "/predict",
            json={"text": "A unique customer message that must not be a label"},
        )
        metrics = client.get("/metrics")

    assert response.status_code == 200
    assert metrics.status_code == 200
    body = metrics.text
    assert "http_requests_total" in body
    assert "http_request_latency_seconds" in body
    assert "nlp_predictions_total" in body
    assert "nlp_prediction_errors_total" in body
    assert "nlp_prediction_latency_seconds" in body
    assert "model_loading_errors_total" in body
    assert "A unique customer message" not in body
    assert "request_id" not in body
    assert "user_id" not in body


def test_metrics_endpoint_has_prometheus_content_type():
    with TestClient(create_app(MetricsPredictor())) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
