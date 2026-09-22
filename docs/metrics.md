# Prometheus metrics

## Metrics architecture

```text
FastAPI middleware and prediction route
  |
  v
Prometheus client registry
  |
  v
GET /metrics
  |
  v
Prometheus scraper
  |
  v
Grafana dashboards
```

The API exposes a custom Prometheus registry through `GET /metrics`.

## Metrics

### HTTP metrics

```text
http_requests_total
http_request_latency_seconds
```

Labels:

```text
method
route
status_class
```

The route label is restricted to known templates:

```text
/health
/health/ready
/model
/predict
/metrics
other
```

### Prediction metrics

```text
nlp_predictions_total
nlp_prediction_errors_total
nlp_prediction_latency_seconds
```

Labels:

```text
prediction
model_version
error_type
```

Error types are restricted to:

```text
not_ready
inference
other
```

### Model loading metrics

```text
model_loading_errors_total
```

Label:

```text
model_source
```

Supported values are:

```text
local
mlflow
other
```

## Cardinality rules

The following are never metric labels:

```text
raw customer text
request ID
user ID
authorization header
exception message
```

This prevents unbounded label growth and protects sensitive input.

## Local verification

```bash
curl http://localhost:8000/metrics
```

Example scrape configuration:

```yaml
scrape_configs:
  - job_name: real-time-nlp-api
    metrics_path: /metrics
    static_configs:
      - targets: ["api:8000"]
```

The API exposes application metrics only. Kubernetes and node-level CPU/memory metrics are collected separately by the Prometheus deployment.
