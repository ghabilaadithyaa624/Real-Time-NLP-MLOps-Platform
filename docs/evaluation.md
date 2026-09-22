# Model evaluation

## Evaluation outputs

`training/evaluate.py` evaluates a saved local Transformer checkpoint and generates:

- accuracy;
- macro precision;
- macro recall;
- macro F1;
- confusion matrix;
- per-class precision, recall, and F1 classification report;
- model and dataset provenance;
- Git commit;
- compute device;
- configurable governance-threshold result.

The artifacts are written to the configured output directory:

```text
evaluation_report.json
confusion_matrix.json
classification_report.json
```

## Validation versus test evaluation

The validation split is used during training for checkpoint selection. The test split is a final holdout and should be evaluated only after the model/checkpoint selection process is complete.

Examples:

```bash
# Checkpoint-selection or governance review
.venv/bin/python -m training.evaluate \
  --config training/config.yaml \
  --model-path artifacts/training \
  --split validation \
  --output-dir artifacts/evaluation-validation

# Final held-out report
.venv/bin/python -m training.evaluate \
  --config training/config.yaml \
  --model-path artifacts/training \
  --split test \
  --output-dir artifacts/evaluation-test
```

The model path must contain the saved Hugging Face model and tokenizer produced by the training phase.

## Governance threshold

The current configurable minimum is:

```yaml
governance:
  metric: f1
  minimum_f1: 0.90
```

The evaluator reports whether the selected split meets the threshold. It does not register a model, assign an MLflow alias, or deploy anything. Deliberate model promotion is implemented separately in the governance phase.

The threshold is configurable because the acceptable quality bar may vary by product, class balance, and the relative cost of false positives and false negatives. A threshold change must be reviewed and recorded; it must not be used to hide a poor result.

## Model versus system performance

This evaluation measures **model performance**:

```text
accuracy
precision
recall
F1
confusion matrix
```

It does not measure API latency, throughput, availability, resource utilization, or error rate. Those belong to system-performance validation and load testing.
