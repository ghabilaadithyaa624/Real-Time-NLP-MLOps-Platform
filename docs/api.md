# FastAPI inference API

## Runtime flow

```text
HTTP request
  |
  v
Request ID middleware
  |
  v
Pydantic validation
  |
  v
In-memory Transformer predictor
  |
  v
Prediction response
```

The model is loaded during application startup and reused across requests. The API does not download or initialize a model inside the request handler.

## Endpoints

### `GET /health`

Process liveness endpoint. It does not require a loaded model so Kubernetes can distinguish a running process from a serving-ready process.

Example response:

```json
{
  "status": "ok",
  "service": "real-time-nlp-api"
}
```

### `GET /health/ready`

Readiness endpoint. It returns HTTP 200 only when the predictor and model are loaded. It returns HTTP 503 when the model is unavailable.

### `GET /model`

Returns non-secret model state:

```json
{
  "status": "ready",
  "model_source": "mlflow",
  "model_version": "production",
  "device": "cpu"
}
```

### `POST /predict`

Request:

```json
{
  "text": "The delivery was extremely fast and the product quality was excellent."
}
```

Response:

```json
{
  "prediction": "positive",
  "confidence": 0.97,
  "model_version": "production",
  "latency_ms": 42.3,
  "request_id": "..."
}
```

The request schema rejects:

- missing `text`;
- empty text;
- whitespace-only text;
- text longer than 10,000 characters;
- unknown fields;
- malformed JSON.

## Model configuration

Production defaults to the MLflow alias:

```text
MODEL_SOURCE=mlflow
MLFLOW_MODEL_URI=models:/customer-feedback-classifier@production
MODEL_VERSION=production
```

Local development can explicitly use a saved Hugging Face directory:

```text
MODEL_SOURCE=local
MODEL_PATH=/path/to/model
MODEL_VERSION=local
```

The predictor also supports:

```text
MAX_LENGTH=128
MODEL_LABELS={"0":"negative","1":"positive"}
```

`MODEL_LABELS` is optional when the model configuration already contains `id2label`.

## Local commands

Start the API with the default production model configuration:

```bash
.venv/bin/uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000
```

For local model testing:

```bash
MODEL_SOURCE=local \
MODEL_PATH=/path/to/saved/model \
MODEL_VERSION=local \
.venv/bin/uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000
```

Test the request:

```bash
curl -X POST http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"text":"The product was fantastic."}'
```

The API returns HTTP 503 rather than serving a fallback model when the configured production model cannot be loaded.
