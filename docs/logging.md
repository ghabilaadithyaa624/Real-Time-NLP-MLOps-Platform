# Structured logging and Loki

## Logging architecture

```text
FastAPI middleware
  |
  v
JSON structured logs to stdout
  |
  v
Docker/Kubernetes log collector
  |
  v
Loki
  |
  v
Grafana Explore and dashboards
```

The application writes JSON to stdout. It does not write application log files inside the container.

## Structured fields

Request completion logs contain:

```json
{
  "timestamp": "2026-09-21T00:00:00+00:00",
  "level": "info",
  "service": "real-time-nlp-api",
  "message": "request.complete",
  "event": "request.complete",
  "request_id": "...",
  "endpoint": "/predict",
  "status_code": 200,
  "latency_ms": 31.2,
  "model_version": "production"
}
```

Model-load events contain:

```text
service
level
event
model_source
model_version
error_type when applicable
```

## Sensitive-data policy

The logging formatter uses an explicit allow-list for extra fields. It never emits:

```text
raw customer text
passwords
AWS credentials
MLflow database passwords
authorization headers
request bodies
```

Request IDs are correlation metadata, not metric labels. Raw text must not be placed in log messages or exception messages.

## Local Loki stack

The optional Docker Compose observability profile runs:

```bash
export GRAFANA_ADMIN_PASSWORD='<local-password>'
docker compose --profile observability up --build
```

The local stack includes:

```text
API
Prometheus
Grafana
Loki
Promtail
```

Loki is available at:

```text
http://localhost:3100
```

Grafana has a provisioned Loki datasource at:

```text
http://loki:3100
```

Search logs in Grafana Explore with queries such as:

```logql
{service="real-time-nlp-api"}
```

```logql
{service="real-time-nlp-api", endpoint="/predict"}
```

Only bounded metadata such as service, level, endpoint, and status code should be promoted to Loki labels. Request IDs remain structured log fields rather than indexed labels.

## Kubernetes direction

In Kubernetes, stdout logs should be collected by a cluster-level Grafana Alloy or pinned equivalent DaemonSet and pushed to Loki. The application does not need Loki credentials or direct network access in its request path.
