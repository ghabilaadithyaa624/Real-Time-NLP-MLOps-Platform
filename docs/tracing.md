# OpenTelemetry tracing

## Scope

The API emits OpenTelemetry traces for:

- FastAPI request handling;
- model loading and warmup;
- prediction/inference work.

The service is named `real-time-nlp-api`. Trace attributes are intentionally
bounded and do not contain customer feedback, request bodies, authorization
headers, credentials, or exception messages.

## Trace shape

```text
HTTP server span
  |
  +--> model.load                 startup only
  |
  +--> nlp.inference              prediction requests
```

The application-defined attributes are allow-listed:

```text
nlp.model.source
nlp.model.version
nlp.model.load.outcome
nlp.inference.device
error.type
```

The FastAPI instrumentation supplies standard HTTP route and status attributes.
Header capture is explicitly disabled, including authorization and cookie
headers. Request IDs are not span attributes or backend index labels.

## Export configuration

Tracing is opt-in. The API remains usable without a collector when:

```text
OTEL_TRACES_EXPORTER=none
```

To export over OTLP/gRPC, set both variables:

```bash
export OTEL_TRACES_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
```

The API supports the OTLP/gRPC exporter. The endpoint must be reachable from
the API process; `localhost` means the API container itself when running in
Compose and is therefore not correct for the local collector.

Optional resource configuration:

```bash
export OTEL_SERVICE_NAME=real-time-nlp-api
export OTEL_DEPLOYMENT_ENVIRONMENT=local
```

## Local Compose usage

The observability profile includes:

```text
API
Prometheus
Grafana
Loki
Promtail
Tempo
OpenTelemetry Collector
```

Start it with tracing enabled:

```bash
export GRAFANA_ADMIN_PASSWORD='<local-password>'
export OTEL_TRACES_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc

docker compose --profile observability up --build
```

The API sends spans to the OpenTelemetry Collector. The collector forwards
spans to Tempo. Grafana provisions Tempo as a datasource at:

```text
http://tempo:3200
```

The local service endpoints are:

```text
Grafana:            http://localhost:3000
Tempo HTTP API:     http://localhost:3200
OTLP gRPC:          localhost:4317
OTLP HTTP:          localhost:4318
```

In Grafana, open **Explore**, select **Tempo**, and search by service name:

```text
real-time-nlp-api
```

Stop the local stack with:

```bash
docker compose --profile observability down
```

Tempo data is stored in the named `tempo-data` volume. It is local
observability state and is excluded from Git.

## Kubernetes/AWS direction

The API should export OTLP to an in-cluster collector service. A production
collector deployment should forward to the managed or platform-approved trace
backend. Do not put cloud credentials in API environment variables or trace
attributes.

The collector and Tempo files in this repository are local Compose
configuration. They are not a claim that an AWS or Kubernetes deployment has
been created.

## Privacy verification

Trace tests assert that a request body and authorization value do not appear
in exported span attributes. Keep the following environment variables unset
unless header capture has an approved, sanitized use case:

```text
OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST
OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_RESPONSE
```

Never add customer text, user identifiers, request IDs, credentials, or raw
exception text to custom span attributes.
