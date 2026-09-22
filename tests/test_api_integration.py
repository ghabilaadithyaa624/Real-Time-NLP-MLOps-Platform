from unittest.mock import Mock
from uuid import UUID

from fastapi.testclient import TestClient

from app.inference.predictor import PredictorNotReady, TransformerPredictor
from app.inference.preprocessing import PreprocessingConfig
from app.main import create_app


def test_real_local_transformer_serves_prediction(tiny_model_path):
    predictor = TransformerPredictor.from_local(
        tiny_model_path,
        preprocessing=PreprocessingConfig(max_length=16),
        model_version="integration-local",
        device="cpu",
    )
    app = create_app(predictor)

    with TestClient(app) as client:
        ready = client.get("/health/ready")
        response = client.post(
            "/predict",
            json={"text": "The product was good."},
        )

    assert ready.status_code == 200
    assert response.status_code == 200
    body = response.json()
    assert body["prediction"] in {"negative", "positive"}
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["model_version"] == "integration-local"
    assert body["latency_ms"] >= 0
    UUID(body["request_id"])


def test_model_load_failure_keeps_liveness_but_blocks_readiness(monkeypatch):
    monkeypatch.setattr(
        "app.main.TransformerPredictor.from_environment",
        Mock(side_effect=PredictorNotReady("registry unavailable")),
    )

    with TestClient(create_app()) as client:
        health = client.get("/health")
        readiness = client.get("/health/ready")
        prediction = client.post("/predict", json={"text": "hello"})

    assert health.status_code == 200
    assert readiness.status_code == 503
    assert prediction.status_code == 503


def test_inference_failure_does_not_expose_internal_error():
    class BrokenPredictor:
        is_ready = True

        def predict(self, text):
            raise RuntimeError("internal model details must not be returned")

    with TestClient(create_app(BrokenPredictor())) as client:
        response = client.post("/predict", json={"text": "hello"})

    assert response.status_code == 500
    assert response.json()["detail"] == "inference failed"
    assert "internal model" not in response.text
