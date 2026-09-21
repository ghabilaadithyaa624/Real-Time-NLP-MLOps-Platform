import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_prometheus_config_scrapes_api_metrics():
    config = yaml.safe_load(
        (ROOT / "monitoring/prometheus.yml").read_text(encoding="utf-8")
    )

    scrape = config["scrape_configs"][0]
    assert scrape["job_name"] == "real-time-nlp-api"
    assert scrape["metrics_path"] == "/metrics"
    assert "api:8000" in scrape["static_configs"][0]["targets"]


def test_grafana_dashboard_contains_required_panels_and_safe_queries():
    dashboard = json.loads(
        (ROOT / "monitoring/grafana/dashboards/customer-feedback.json").read_text(
            encoding="utf-8"
        )
    )
    titles = {panel["title"] for panel in dashboard["panels"]}
    required = {
        "Requests per second",
        "Predictions per second",
        "Prediction error rate",
        "HTTP latency p50",
        "HTTP latency p95",
        "HTTP latency p99",
        "Prediction distribution",
        "Inference latency p95",
        "Pod CPU usage",
        "Pod memory usage",
        "Ready pod count",
    }
    assert required <= titles
    serialized = json.dumps(dashboard)
    assert "raw_text" not in serialized
    assert "request_id" not in serialized
    assert "user_id" not in serialized
