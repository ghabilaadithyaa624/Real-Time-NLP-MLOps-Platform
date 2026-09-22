from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.inference.predictor import PredictionResult
from app.main import create_app


@dataclass
class AuthPredictor:
    model_version: str = "auth-test"
    model_source: str = "test"
    device: str = "cpu"
    is_ready: bool = True

    def predict(self, text: str) -> PredictionResult:
        return PredictionResult(
            prediction="positive",
            confidence=0.9,
            model_version=self.model_version,
        )


def test_authentication_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("API_AUTH_MODE", raising=False)
    monkeypatch.delenv("API_AUTH_TOKEN", raising=False)

    with TestClient(create_app(AuthPredictor())) as client:
        response = client.get("/model")

    assert response.status_code == 200


def test_bearer_auth_protects_application_routes_but_not_health(monkeypatch):
    monkeypatch.setenv("API_AUTH_MODE", "bearer")
    monkeypatch.setenv("API_AUTH_TOKEN", "runtime-only-test-token")

    with TestClient(create_app(AuthPredictor())) as client:
        health = client.get("/health")
        missing = client.get("/model")
        invalid = client.get(
            "/model",
            headers={"Authorization": "Bearer wrong-token"},
        )
        valid = client.get(
            "/model",
            headers={"Authorization": "Bearer runtime-only-test-token"},
        )

    assert health.status_code == 200
    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert invalid.headers["WWW-Authenticate"] == "Bearer"
    assert valid.status_code == 200
    assert "runtime-only-test-token" not in invalid.text


def test_bearer_mode_fails_closed_when_token_is_not_configured(monkeypatch):
    monkeypatch.setenv("API_AUTH_MODE", "bearer")
    monkeypatch.delenv("API_AUTH_TOKEN", raising=False)

    with TestClient(create_app(AuthPredictor())) as client:
        response = client.get("/model")

    assert response.status_code == 503
    assert response.json() == {"detail": "authentication is not configured"}
