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

## Local PostgreSQL and S3-compatible profile

For local integration testing of the production storage boundary, Compose
provides an explicit `mlflow` profile:

```text
PostgreSQL 16       -> MLflow backend store and registry metadata
MinIO                -> S3-compatible MLflow artifact store
MLflow 2.19.0       -> tracking server and model registry API
```

Set runtime-only credentials and start the profile:

```bash
export MLFLOW_POSTGRES_PASSWORD='<local-password>'
export MINIO_ROOT_USER='minio-local'
export MINIO_ROOT_PASSWORD='<local-minio-password>'

docker compose --profile mlflow up -d mlflow
```

The local endpoints are:

```text
MLflow:       http://localhost:5000
MinIO API:    http://localhost:9000
MinIO console: http://localhost:9001
PostgreSQL:   internal Compose service `postgres:5432`
```

For training commands running on the host, point MLflow at the published
server:

```bash
MLFLOW_TRACKING_URI=http://localhost:5000 \
  .venv/bin/python -m training.train \
    --config training/config.yaml \
    --with-mlflow \
    --output-dir artifacts/training
```

The Compose MLflow server uses a PostgreSQL URI for `--backend-store-uri`
and an `s3://` default artifact root. The MinIO credentials are injected only
at runtime. They are not stored in Compose files, YAML configuration, GitHub
Actions, or Git.

Stop the profile without deleting named data volumes:

```bash
docker compose --profile mlflow down
```

Delete local state only when intentionally resetting the integration
environment:

```bash
docker compose --profile mlflow down --volumes
```

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
