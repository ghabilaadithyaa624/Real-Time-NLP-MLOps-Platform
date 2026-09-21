"""Locust workload for the customer feedback API.

The payload is fixed synthetic text. Do not replace it with customer data.
"""

from __future__ import annotations

from locust import HttpUser, between, task

SYNTHETIC_TEXT = "Synthetic load-test feedback for the customer feedback API."


class CustomerFeedbackUser(HttpUser):
    """Exercise the public API contract with bounded request names."""

    wait_time = between(1.0, 3.0)

    @task(8)
    def predict(self) -> None:
        with self.client.post(
            "/predict",
            name="/predict",
            json={"text": SYNTHETIC_TEXT},
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"status_code={response.status_code}")
                return
            try:
                payload = response.json()
            except ValueError:
                response.failure("invalid_json")
                return
            if not {
                "prediction",
                "confidence",
                "model_version",
                "latency_ms",
                "request_id",
            }.issubset(payload):
                response.failure("invalid_prediction_response")
                return
            if payload["prediction"] not in {"positive", "negative"}:
                response.failure("invalid_prediction_label")

    @task(1)
    def health(self) -> None:
        with self.client.get("/health", name="/health", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"status_code={response.status_code}")

    @task(1)
    def readiness(self) -> None:
        with self.client.get(
            "/health/ready",
            name="/health/ready",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"status_code={response.status_code}")

    @task(1)
    def model_metadata(self) -> None:
        with self.client.get("/model", name="/model", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"status_code={response.status_code}")
