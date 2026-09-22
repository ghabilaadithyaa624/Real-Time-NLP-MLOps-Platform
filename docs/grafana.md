# Grafana dashboards

## Provisioning architecture

```text
Prometheus
  |
  v
Grafana Prometheus datasource
  |
  v
Provisioned Customer Feedback Intelligence dashboard
```

The repository provisions:

```text
monitoring/grafana/provisioning/datasources/prometheus.yml
monitoring/grafana/provisioning/dashboards/dashboards.yml
monitoring/grafana/dashboards/customer-feedback.json
```

The dashboard uses a stable Prometheus datasource UID and can be loaded without manually recreating panels.

## Dashboard panels

| Panel | Purpose |
|---|---|
| Requests per second | Overall HTTP traffic rate |
| Predictions per second | Successful inference throughput |
| Prediction error rate | Failed prediction ratio |
| HTTP latency p50 | Typical request latency |
| HTTP latency p95 | Tail latency for most requests |
| HTTP latency p99 | Extreme request tail latency |
| Prediction distribution | Positive/negative output rate |
| Inference latency p95 | Model execution tail latency |
| Pod CPU usage | Container CPU consumption |
| Pod memory usage | Container memory working set |
| Ready pod count | Kubernetes serving capacity and health |

## Required data sources

Application panels require the API metrics from `GET /metrics`.

CPU, memory, and pod readiness panels require Kubernetes exporters such as:

- cAdvisor metrics exposed through kubelet/Prometheus;
- kube-state-metrics for pod readiness and metadata.

If those exporters are not installed, the application panels still work but infrastructure panels remain empty.

## PromQL design

Latency panels use histogram quantiles:

```promql
histogram_quantile(
  0.95,
  sum by (le) (rate(http_request_latency_seconds_bucket[5m]))
)
```

Throughput panels use rates over a five-minute window:

```promql
sum(rate(http_requests_total[5m]))
```

The error-rate panel divides prediction errors by total prediction attempts and clamps the denominator to avoid division by zero.

## Local usage

The optional Docker Compose observability profile runs Prometheus and Grafana with the provisioned dashboard:

```bash
export GRAFANA_ADMIN_PASSWORD='<local-password>'
docker compose --profile observability up --build
```

The local endpoints are:

```text
Prometheus: http://localhost:9090
Grafana:    http://localhost:3000
```

The dashboard files are mounted into Grafana using the provisioning paths. The Prometheus target is configured as:

```text
api:8000/metrics
```

This hostname is appropriate for Docker Compose networking. Kubernetes deployments should use the Kubernetes Service and service discovery configuration instead.

## Interpretation guidance

- High requests/sec with low predictions/sec may indicate validation or upstream traffic issues.
- Rising p95/p99 with stable model metrics may indicate CPU pressure, sequence-length changes, or queueing.
- A prediction distribution shift is not automatically a model failure; it requires data-drift investigation.
- A ready-pod count of zero is an availability issue even if model F1 is high.
- CPU and memory panels measure system performance, not model quality.
