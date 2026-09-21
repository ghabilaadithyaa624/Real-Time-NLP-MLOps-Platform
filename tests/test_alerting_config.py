import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_prometheus_loads_alert_rules():
    prometheus = yaml.safe_load(
        (ROOT / "monitoring/prometheus.yml").read_text(encoding="utf-8")
    )
    alerts = yaml.safe_load(
        (ROOT / "monitoring/prometheus-alerts.yml").read_text(encoding="utf-8")
    )

    assert prometheus["rule_files"] == ["/etc/prometheus/alerts.yml"]
    rules = alerts["groups"][0]["rules"]
    names = {rule["alert"] for rule in rules}
    assert names == {
        "CustomerFeedbackApiTargetDown",
        "CustomerFeedbackApiHttp5xxRateHigh",
        "CustomerFeedbackApiPredictionErrorRateHigh",
        "CustomerFeedbackApiPredictionLatencyHigh",
        "CustomerFeedbackApiModelLoadingFailure",
    }
    assert all("for" in rule for rule in rules)


def test_alert_rules_use_bounded_metrics_and_no_sensitive_fields():
    text = (ROOT / "monitoring/prometheus-alerts.yml").read_text(encoding="utf-8")
    assert "request_id" not in text
    assert "user_id" not in text
    assert "raw_text" not in text
    assert "Authorization" not in text
    assert "nlp_prediction_latency_seconds_bucket" in text
    assert "status_class=~\"5xx\"" in text


def test_compose_mounts_the_prometheus_rule_file():
    compose = yaml.safe_load(
        (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    volumes = compose["services"]["prometheus"]["volumes"]
    assert "./monitoring/prometheus-alerts.yml:/etc/prometheus/alerts.yml:ro" in volumes


def test_alert_rule_json_serialization_is_safe():
    alerts = yaml.safe_load(
        (ROOT / "monitoring/prometheus-alerts.yml").read_text(encoding="utf-8")
    )
    serialized = json.dumps(alerts)
    assert "private customer message" not in serialized.lower()
    assert "request_id" not in serialized
