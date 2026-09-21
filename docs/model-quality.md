# Model-quality telemetry

## Confidence metric

Successful predictions expose a bounded Prometheus histogram:

```text
nlp_prediction_confidence{model_version="..."}
```

The histogram is bucketed from 0.0 to 1.0 and uses only `model_version` as a
label. The API clamps unexpected values to that range before recording them.
It never records customer text, request IDs, user IDs, or raw inputs.

The Grafana dashboard includes:

```text
Low-confidence prediction share
```

The panel shows the proportion of successful predictions with confidence at or
below 0.7 over the selected time window.

## Interpretation

Confidence is an operational signal, not ground-truth accuracy. A high or low
confidence distribution can result from:

- model calibration;
- class balance changes;
- input distribution changes;
- preprocessing changes;
- model version changes;
- adversarial or malformed traffic.

Do not promote or roll back a model from confidence telemetry alone. Use the
existing labeled evaluation and governance workflow for promotion decisions.

## Investigation workflow

When the confidence distribution changes:

1. identify the model version;
2. compare the deployment image and preprocessing configuration;
3. compare traffic volume and endpoint error rate;
4. inspect aggregate latency and readiness metrics;
5. run the approved evaluation set;
6. run a controlled load test if capacity or latency changed;
7. record the decision and evidence in the model governance system.

Raw customer text must not be copied into dashboards, alert labels, traces,
logs, or incident metadata.

## Limitations

The metric does not provide calibrated probability guarantees and does not
measure accuracy without labels. It is intentionally a low-cardinality runtime
signal that complements, rather than replaces, offline evaluation.
