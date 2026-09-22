# Prometheus SLO alerting

## Scope

Prometheus now loads `monitoring/prometheus-alerts.yml` and evaluates bounded
rules for the API:

```text
CustomerFeedbackApiTargetDown
CustomerFeedbackApiHttp5xxRateHigh
CustomerFeedbackApiPredictionErrorRateHigh
CustomerFeedbackApiPredictionLatencyHigh
CustomerFeedbackApiModelLoadingFailure
```

The rules use existing low-cardinality metrics. They do not use raw customer
text, request bodies, request IDs, user IDs, or arbitrary exception strings.

## Thresholds

The initial rules use these provisional thresholds:

```text
HTTP 5xx rate:             > 5% for 10 minutes
Prediction error rate:     > 1% for 10 minutes
Prediction p95 latency:    > 500 ms for 10 minutes
Model-load failures:       any increase sustained for 5 minutes
Scrape target down:        2 minutes
```

These thresholds are alerting defaults, not measured service-level results.
They must be calibrated against the load-testing profile and approved SLOs.

## Local verification

Start the observability profile with a local model available:

```bash
export GRAFANA_ADMIN_PASSWORD='<local-password>'
docker compose --profile observability up --build
```

Open Prometheus:

```text
http://localhost:9090/alerts
```

The alert rules should appear after Prometheus reloads its configuration.
Verify rule syntax in a Docker-enabled environment with:

```bash
docker compose --profile observability config
```

This repository does not include an Alertmanager service. Prometheus rule
states alone do not deliver email, PagerDuty, Slack, or other notifications.
Configure an approved Alertmanager, managed Prometheus, or cloud notification
integration for each environment.

## Response guidance

### Target down

Check:

```bash
kubectl -n customer-feedback get pods,svc
kubectl -n customer-feedback logs deployment/feedback-api
```

### HTTP 5xx or prediction errors

Correlate the alert window with:

```text
structured request.complete logs
Loki service and endpoint fields
OpenTelemetry request and nlp.inference spans
model_version
```

Do not add request bodies or customer text to the incident record.

### Prediction latency

Compare the alert with:

```text
model version
replica count
CPU and memory saturation
input length distribution, if separately approved
recent image or preprocessing changes
```

Run the documented load-test procedure before changing capacity targets.

### Model loading failure

Readiness should remain false. Verify the MLflow production alias, artifact
permissions, KMS access, and model registry availability before restarting or
promoting any model.

## Verification boundary

The rule file and Prometheus configuration are statically validated in tests.
No Prometheus server, Alertmanager, notification channel, or production alert
has been run or configured by this phase.
