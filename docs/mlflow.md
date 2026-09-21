# MLflow experiment tracking and model registry

## Local architecture

```text
training/train.py
  |
  | optional --with-mlflow
  v
MLflow Tracking Server / local file backend
  |
  +-- run parameters
  +-- run metrics
  +-- dataset metadata
  +-- training configuration
  +-- Transformer model artifact
  v
MLflow Model Registry
  |
  +-- customer-feedback-classifier
  +-- candidate alias
  +-- production alias (assigned only in governance/promotion phase)
```

The local default is:

```yaml
mlflow:
  enabled: false
  tracking_uri: file:./mlruns
```

MLflow is opt-in for local training so a normal CPU training run does not silently require a tracking service. Production enables tracking through configuration or `MLFLOW_TRACKING_URI`.

## What is tracked

The integration records:

- model name and pinned revision;
- dataset name and pinned revision;
- random seed and validation split;
- maximum sequence length;
- batch size;
- learning rate;
- epoch count;
- governance threshold;
- compute device;
- Git commit;
- training and validation metrics;
- per-step loss and learning-rate history;
- dataset metadata;
- training configuration;
- Hugging Face Transformer model artifact.

The model is logged using the MLflow Transformers flavor, so the model and tokenizer remain a single loadable artifact.

## Commands

Enable MLflow for a training run through the configuration or command-line flag:

```bash
.venv/bin/python -m training.train \
  --config training/config.yaml \
  --with-mlflow \
  --output-dir artifacts/training
```

The command prints a result containing the MLflow `run_id` and model URI. The same information is included in `training_summary.json`.

Register the run artifact as a candidate model version:

```bash
.venv/bin/python -m training.register_model \
  --config training/config.yaml \
  --run-id <RUN_ID> \
  --alias candidate
```

This command refuses to assign the `production` alias. Production promotion is a separate governance action and will be implemented later.

## Production storage

The local `file:./mlruns` backend is for development only. The production target is:

```text
MLflow Tracking Server
  |
  +-- PostgreSQL: run metadata and registry state
  +-- S3: model artifacts
```

Production tracking and registry URIs are supplied through deployment configuration. Database passwords and AWS credentials are not stored in this repository.
