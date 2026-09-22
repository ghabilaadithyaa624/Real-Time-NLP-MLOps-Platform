# API load testing

## Safety boundary

The Locust workload sends one fixed synthetic payload:

```text
Synthetic load-test feedback for the customer feedback API.
```

Do not replace it with customer feedback, credentials, tokens, or production
request bodies. The request names are fixed to bounded endpoint names so
Locust output cannot create high-cardinality series.

## Prerequisites

The API must already be running with a loaded model:

```bash
curl --fail http://localhost:8000/health/ready
```

Start a local API with a known model using the documented Docker or local
serving workflow. Load testing is not a substitute for readiness verification.

## Baseline run

From the repository root:

```bash
mkdir -p load_test_results
locust \
  --headless \
  --locustfile load_testing/locustfile.py \
  --host http://localhost:8000 \
  --users 10 \
  --spawn-rate 2 \
  --run-time 5m \
  --csv load_test_results/baseline \
  --html load_test_results/baseline.html
```

Check the prediction SLOs:

```bash
python load_testing/check_results.py \
  load_test_results/baseline_stats.csv \
  --max-p95-ms 500 \
  --max-p99-ms 1000 \
  --max-error-rate 0.01
```

The checker exits with status `0` only when the measured Locust row meets the
thresholds. It exits with status `1` when a threshold is exceeded.

## SLOs

These are provisional acceptance targets, not measured results:

```text
POST /predict p95 <= 500 ms
POST /predict p99 <= 1000 ms
POST /predict error rate <= 1%
```

Record each run with:

```text
Git SHA
image digest
model version
model source
replica count
node instance type
Locust users and spawn rate
run duration
CPU and memory limits
```

Run a short ramp test before a longer soak test. Repeat after model,
preprocessing, instance-type, or autoscaling changes. Compare results only
when the environment and workload parameters are comparable.

## Result handling

CSV and HTML output belongs in `load_test_results/`, which is ignored by Git.
Do not commit generated results containing private hostnames, access tokens,
or customer data.

No benchmark result is reported by this repository phase. A result exists
only after the command is executed against a specified deployment and the
parameters above are recorded.
