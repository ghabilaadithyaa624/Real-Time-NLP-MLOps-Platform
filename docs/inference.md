# Real-time inference hardening

## Model lifecycle

```text
Application startup
  |
  +-- read validated environment settings
  +-- load tokenizer once
  +-- load model once
  +-- move model to CPU or CUDA
  +-- model.eval()
  +-- warmup inference
  v
Ready to serve
  |
  +-- normalize and tokenize request
  +-- tensor conversion
  +-- torch.inference_mode()
  +-- logits -> softmax -> class/confidence
  +-- return model version and latency
```

The request path never calls `from_pretrained`, `mlflow.load_model`, or model initialization. Model loading failures happen at startup and leave the service unready.

## Production defaults

```text
MODEL_SOURCE=mlflow
MLFLOW_MODEL_URI=models:/customer-feedback-classifier@production
MODEL_VERSION=production
MAX_LENGTH=128
INFERENCE_DEVICE=auto
```

The local mode is explicit:

```text
MODEL_SOURCE=local
MODEL_PATH=/path/to/model
MODEL_VERSION=local
```

The `MODEL_LABELS` environment variable is optional. When omitted, labels are read from the model's `id2label` configuration.

## Runtime safety

- `torch.inference_mode()` disables gradient tracking;
- the model is put into evaluation mode;
- CPU fallback is automatic;
- CUDA is used only when available and selected;
- confidence is derived from softmax probabilities;
- malformed or empty input is rejected before model execution;
- internal model-loading errors are not returned to clients;
- unavailable models produce HTTP 503 rather than an unapproved fallback;
- the response includes the configured model version for traceability.

## Failure behavior

| Failure | Behavior |
|---|---|
| MLflow unavailable at startup | liveness remains available; readiness is false |
| Local model path missing | readiness is false |
| Invalid model source | readiness is false |
| Tokenization failure | request returns a generic inference error |
| Model forward failure | request returns a generic inference error |
| Invalid request | FastAPI returns HTTP 422 |

Internal exception details are retained in server logs for later structured logging, but are not sent in the prediction response.
