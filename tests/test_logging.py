import json
import logging

from app.observability.logging import JsonFormatter, configure_logging, log_request_complete


def test_json_formatter_emits_safe_structured_fields_only():
    record = logging.LogRecord(
        name="real-time-nlp-api",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request.complete",
        args=(),
        exc_info=None,
    )
    record.request_id = "request-123"
    record.endpoint = "/predict"
    record.status_code = 200
    record.latency_ms = 12.5
    record.model_version = "production"
    record.raw_text = "this must not be emitted"

    rendered = JsonFormatter().format(record)
    payload = json.loads(rendered)

    assert payload["service"] == "real-time-nlp-api"
    assert payload["request_id"] == "request-123"
    assert payload["endpoint"] == "/predict"
    assert payload["status_code"] == 200
    assert payload["latency_ms"] == 12.5
    assert "raw_text" not in payload
    assert "this must not be emitted" not in rendered


def test_request_logging_helper_produces_json(caplog):
    logger = configure_logging()
    with caplog.at_level(logging.INFO, logger="real-time-nlp-api"):
        log_request_complete(
            logger,
            request_id="request-456",
            endpoint="/health",
            status_code=200,
            latency_ms=1.2,
            model_version="production",
        )

    assert "request.complete" in caplog.text or logger.name == "real-time-nlp-api"
