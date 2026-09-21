from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.inference.predictor import PredictionResult
from app.main import create_app


@dataclass
class FakePredictor:
    model_version: str = "production"
    model_source: str = "test"
    device: str = "cpu"
    is_ready: bool = True

    def predict(self, text: str) -> PredictionResult:
        assert text
        return PredictionResult(
            prediction="positive",
            confidence=0.98,
            model_version=self.model_version,
        )


def test_health_and_model_endpoints():
    with TestClient(create_app(FakePredictor())) as client:
        assert client.get("/health").json() == {
            "status": "ok",
            "service": "real-time-nlp-api",
        }
        assert client.get("/health/ready").status_code == 200
        assert client.get("/model").json() == {
            "status": "ready",
            "model_source": "test",
            "model_version": "production",
            "device": "cpu",
        }


def test_predict_response_and_request_id():
    with TestClient(create_app(FakePredictor())) as client:
        response = client.post(
            "/predict",
            json={"text": "The delivery was excellent."},
            headers={"X-Request-ID": "request-test-123"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["prediction"] == "positive"
    assert body["confidence"] == 0.98
    assert body["model_version"] == "production"
    assert body["request_id"] == "request-test-123"
    assert body["latency_ms"] >= 0
    assert response.headers["X-Request-ID"] == "request-test-123"


def test_invalid_requests_are_rejected():
    with TestClient(create_app(FakePredictor())) as client:
        assert client.post("/predict", json={"text": "   "}).status_code == 422
        assert client.post("/predict", json={}).status_code == 422
        assert client.post("/predict", json={"text": "x", "extra": 1}).status_code == 422
        assert client.post("/predict", content="not-json").status_code == 422
        assert client.post("/predict", json={"text": "x" * 10_001}).status_code == 422


def test_unready_model_returns_service_unavailable():
    predictor = FakePredictor(is_ready=False)
    with TestClient(create_app(predictor)) as client:
        assert client.get("/health/ready").status_code == 503
        assert client.post("/predict", json={"text": "hello"}).status_code == 503
