from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.inference.predictor import PredictionResult
from app.main import create_app


@dataclass
class SecurityPredictor:
    model_version: str = "security-test"
    model_source: str = "test"
    device: str = "cpu"
    is_ready: bool = True

    def predict(self, text: str) -> PredictionResult:
        return PredictionResult(
            prediction="positive",
            confidence=0.9,
            model_version=self.model_version,
        )


def test_json_api_security_headers_are_present(monkeypatch):
    monkeypatch.delenv("ENABLE_HSTS", raising=False)

    with TestClient(create_app(SecurityPredictor())) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Permissions-Policy"] == (
        "camera=(), microphone=(), geolocation=()"
    )
    assert response.headers["Content-Security-Policy"] == (
        "default-src 'none'; frame-ancestors 'none'"
    )
    assert response.headers["Cache-Control"] == "no-store"
    assert "Strict-Transport-Security" not in response.headers


def test_hsts_is_explicitly_opt_in(monkeypatch):
    monkeypatch.setenv("ENABLE_HSTS", "true")

    with TestClient(create_app(SecurityPredictor())) as client:
        response = client.get("/health")

    assert response.headers["Strict-Transport-Security"] == (
        "max-age=31536000; includeSubDomains"
    )
