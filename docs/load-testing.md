# Load testing and API SLOs

The repository includes a Locust scenario under `load_testing/`. It exercises
`/predict`, `/health`, `/health/ready`, and `/model` using fixed synthetic text.
It does not ingest customer data.

## Run procedure

1. Deploy the exact API image and model version to a dedicated test target.
2. Confirm model readiness:

   ```bash
   curl --fail https://<test-host>/health/ready
   ```

3. Record the Git SHA, image digest, model version, replica count, node type,
   CPU/memory limits, and target URL.
4. Run the baseline:

   ```bash
   mkdir -p load_test_results
   locust \
     --headless \
     --locustfile load_testing/locustfile.py \
     --host https://<test-host> \
     --users 10 \
     --spawn-rate 2 \
     --run-time 5m \
     --csv load_test_results/baseline
   ```

5. Check the generated prediction statistics:

   ```bash
   python load_testing/check_results.py \
     load_test_results/baseline_stats.csv
   ```

6. Store the report in an approved performance-results system, not in Git.

## Thresholds

The checker defaults to these provisional targets:

```text
p95 <= 500 ms
p99 <= 1000 ms
error rate <= 1%
```

They are targets only. They are not benchmark results and must be reviewed
against the deployment's model, hardware, replica count, and traffic profile.

Use stricter or looser thresholds explicitly when approved:

```bash
python load_testing/check_results.py \
  load_test_results/baseline_stats.csv \
  --max-p95-ms 750 \
  --max-p99-ms 1500 \
  --max-error-rate 0.005
```

## Workload privacy

The load test payload is hard-coded as synthetic text. Request names remain
bounded (`/predict`, `/health`, `/health/ready`, `/model`). Do not add request
IDs, customer identifiers, authorization headers, or arbitrary text to Locust
labels or task names.

The API's existing logging, metrics, and tracing policies remain in force:
raw request bodies are not added to logs, Prometheus labels, Loki labels, or
custom trace attributes.

## Limitations

A Locust result from one laptop or one sandbox is not a production capacity
claim. Meaningful capacity testing requires the deployment topology, model
artifact, CPU architecture, autoscaling policy, and network path to match the
intended environment.

The current sandbox does not contain a running production deployment. No load
benchmark or SLO result is claimed by this phase.
