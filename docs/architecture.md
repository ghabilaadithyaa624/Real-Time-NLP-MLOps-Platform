# Real-Time NLP MLOps Platform Architecture

## Purpose

The platform classifies customer feedback as `positive` or `negative` through a synchronous FastAPI API. It separates the **online serving plane** from the **offline ML lifecycle plane** so that inference remains small and predictable while training, evaluation, registration, and promotion remain auditable.

This document is the Phase 1 architecture checkpoint. It describes the target design; it does not claim that any service has been deployed or that any model has been trained.

## Architecture principles

1. **Synchronous inference first.** A request is classified in the API process. A queue or stream processor is not needed for the initial low-latency request/response contract.
2. **Load once, infer many times.** A serving process resolves the configured model at startup and keeps the tokenizer and model in memory. It never downloads a model on every request.
3. **Registry-controlled production.** The API's production default is `models:/customer-feedback-classifier@production`. The `production` alias points to a validated immutable model version; it is changed only by an explicit promotion operation.
4. **Configuration outside code.** Model name, source, MLflow URI, sequence length, thresholds, and observability endpoints are environment/configuration values.
5. **No raw feedback in telemetry.** Logs, metrics labels, and trace attributes contain request and model metadata, never customer text.
6. **Stateless API pods.** Model artifacts are cached in the pod filesystem or an ephemeral volume. Durable model artifacts belong in object storage, not in a container image or pod volume.
7. **Graceful dependency failure.** A pod whose model cannot be loaded is not ready to receive traffic. An already-loaded model can continue serving if the registry has a transient outage; a new rollout must not silently fall back to an unapproved model.
8. **Reproducible lifecycle.** Dataset revision, configuration, Git commit, model version, and evaluation results are recorded with each training run.

## System context

```text
                                      Offline ML lifecycle
  IMDb (pinned HF dataset revision)
                 |
                 v
  deterministic split + preprocessing + tokenizer
                 |
                 v
  Transformer fine-tuning (DistilBERT by default)
                 |
                 v
  evaluation + governance threshold + model card
                 |
                 v
  MLflow Tracking Server -----------------------> PostgreSQL
          |                                          (metadata,
          |                                           registry)
          v
  S3 model artifacts <---- registered model version
                 |
                 | explicit, audited promotion of a validated version
                 v
       MLflow alias: customer-feedback-classifier@production
                 |
                 | startup-only model resolution
                 v
  ---------------------------------------------------------------
                         Online serving
  Client -> HTTPS Ingress/API auth -> FastAPI -> prediction response
                                              |
                         +--------------------+--------------------+
                         |                    |                    |
                       metrics              logs                traces
                         |                    |                    |
                    Prometheus             Loki             OTel Collector
                         |                    |                    |
                      Grafana              Grafana             Tempo
```

## Online request path

```text
Client
  |
  | POST /predict {"text": "..."}
  v
HTTPS load balancer / Kubernetes Ingress
  |  TLS termination, network boundary, optional auth/rate limiting
  v
FastAPI application pod
  |
  +--> request-ID middleware
  |      generate or validate a bounded correlation ID
  |
  +--> Pydantic request validation
  |      reject missing, empty, malformed, or over-limit text
  |
  +--> deterministic preprocessing
  |      normalization policy, tokenizer, truncation, padding,
  |      attention mask, configured max sequence length
  |
  +--> in-memory Transformer predictor
  |      inference_mode/no_grad, logits -> probabilities -> label
  |
  +--> response schema
         prediction, confidence, model_version, latency_ms, request_id

Other endpoints:
  GET /health        process/liveness signal; no external dependency check
  GET /health/ready  model loaded and usable; controls traffic admission
  GET /model         non-secret model identity and load status
  GET /metrics       Prometheus exposition endpoint
```

### Serving behavior

- `MODEL_SOURCE=local` loads a local Hugging Face model directory for development and tests.
- `MODEL_SOURCE=mlflow` is the production path. The process resolves the configured MLflow model URI at startup, downloads the artifact through the MLflow/S3 path, and loads the tokenizer and model once.
- The inference adapter hides the model loader behind a small interface. Replacing DistilBERT with another compatible sequence-classification Transformer changes configuration/model packaging rather than every route.
- The API exposes the model version or alias in the response and in low-cardinality telemetry. It does not expose credentials, artifact URLs, or raw feedback.
- A load failure is logged as a structured error and increments a model-loading metric. Readiness remains false. The deployment rollout is therefore blocked rather than serving an unapproved or partially initialized model.

## Offline ML lifecycle

```text
Pinned IMDb dataset revision
  |
  v
training/dataset.py
  deterministic train/validation split, class mapping, dataset metadata
  |
  v
Tokenizer + preprocessing configuration
  max_length, batch_size, learning_rate, epochs, model_name, seed
  |
  v
training/train.py
  Hugging Face Datasets + Transformers + PyTorch
  CUDA when available, CPU fallback, best checkpoint by validation F1
  |
  +--> MLflow run: parameters, metrics, config, Git commit, dataset info,
  |                  confusion matrix/report, model artifact
  |
  v
training/evaluate.py
  accuracy, precision, recall, F1, confusion matrix, report
  |
  v
training/governance.py
  configurable minimum validation F1 (for example 0.90)
  candidate | validated | rejected
  |
  v
training/register_model.py
  register the validated artifact as customer-feedback-classifier
  |
  v
training/promote_model.py
  explicit human/automation-approved operation:
  validated version -> production alias
  record version, metric, timestamp, dataset, model type, Git commit
  |
  v
MLflow Model Registry: @production
```

Training, evaluation, registration, and promotion are separate commands. A successful training run is not itself a production promotion. The threshold is configurable because the acceptable trade-off between false positives and false negatives may change by product or dataset; it must still be enforced and recorded for each promotion decision.

### MLflow storage boundary

```text
MLflow Tracking/Registry Server
  |
  +--> PostgreSQL: experiment/run metadata and model registry state
  |
  +--> S3: model files, tokenizer, evaluation artifacts, reports
```

S3 is never used as the MLflow metadata database. In local development, a Postgres container and an S3-compatible local object store can reproduce this boundary; production uses managed PostgreSQL (RDS) and an encrypted S3 bucket. The application does not need a prediction database for the initial design.

## Observability architecture

```text
FastAPI
  |
  +--> Prometheus scrape /metrics
  |       nlp_predictions_total
  |       nlp_prediction_errors_total
  |       nlp_prediction_latency_seconds
  |       http_requests_total
  |       http_request_latency_seconds
  |       model_loading_errors_total
  |              |
  |              v
  |           Grafana
  |
  +--> JSON logs to stdout
  |       timestamp, level, service, request_id, endpoint,
  |       status_code, latency_ms, model_version, error type
  |              |
  |       Kubernetes log collector (Grafana Alloy or pinned equivalent)
  |              |
  |              v
  |             Loki -> Grafana Explore/dashboards
  |
  +--> OpenTelemetry FastAPI/request/predictor spans
          model_name, model_version, endpoint, status_code
                    |
                    v
             OTLP Collector -> Tempo -> Grafana
```

Metrics use bounded labels such as route, method, status class, prediction class, and model version. Raw text, request IDs, user IDs, and arbitrary exception strings are not metric labels. Logs are structured and searchable but intentionally omit sensitive feedback and authorization material. Trace spans cover HTTP handling, preprocessing/tokenization, and model inference without putting customer text in span attributes.

The application emits metrics directly for simple Prometheus scraping. OpenTelemetry is used for traces and can later be extended to other services; this avoids requiring a metrics gateway for the initial deployment.

## Deployment architecture

### Local development

```text
Docker Compose
  +-- FastAPI API
  +-- MLflow server
  +-- PostgreSQL (MLflow backend)
  +-- S3-compatible object store or explicit local artifact profile
  +-- Prometheus + Grafana
  +-- Loki + log collector
  +-- OpenTelemetry Collector + Tempo (optional observability profile)
```

Local profiles will allow the API and tests to run without the full monitoring stack. Local model mode is explicit; it is not used to mask a broken production registry configuration.

### Kubernetes and AWS

```text
AWS VPC
  |
  +-- EKS cluster
  |     |
  |     +-- feedback API Deployment (multiple replicas, non-root)
  |     +-- internal MLflow Deployment (or separately managed service)
  |     +-- Prometheus/Grafana/Loki/Tempo observability workloads
  |     +-- Kubernetes Service + AWS load-balancer Ingress
  |     +-- ServiceAccount with workload identity for S3
  |
  +-- ECR: immutable API images tagged by Git SHA
  +-- S3: encrypted MLflow artifacts
  +-- RDS PostgreSQL: MLflow backend and registry metadata
```

Terraform owns the AWS infrastructure boundary: VPC, EKS, ECR, S3, RDS, IAM/workload identity, and required security groups. Kubernetes manifests own application workloads and configuration. The repository will use a base/overlay layout to avoid duplicating manifests between local and AWS environments; flat files can still be generated or referenced from those overlays.

For production, RDS is preferred to a PostgreSQL StatefulSet on EKS. A Kubernetes PostgreSQL manifest is useful for local or non-production demonstrations, but the production MLflow metadata store must have managed backups, encryption, and recovery procedures.

## CI/CD flow

```text
Pull request
  -> lint/type/basic security checks
  -> unit and integration tests
  -> Docker build (no production deployment)

Protected main/release workflow
  -> repeat validation
  -> build image tagged with Git SHA
  -> push to ECR
  -> GitHub OIDC assumes a narrowly scoped AWS role
  -> deploy immutable image to EKS
  -> wait for rollout and readiness
  -> smoke-test /health and /predict
```

Production deployment is restricted to protected branches/environments and uses GitHub OIDC rather than long-lived AWS access keys. Deployment should pin the image by Git SHA (and preferably digest after push), never by `latest`. No credential is baked into an image, committed to Git, or placed in a normal ConfigMap.

## Security boundaries

- HTTPS terminates at the configured load balancer/Ingress. Authentication and rate limiting are enabled at the production boundary and are disabled only through an explicit local-development profile.
- API validation limits payload size and text length before tokenization.
- Pods use a non-root user, a read-only root filesystem where compatible, dropped Linux capabilities, resource limits, and a dedicated ServiceAccount.
- S3 and AWS APIs are accessed through EKS workload identity; containers do not receive long-lived AWS keys.
- Database passwords, MLflow credentials, and other secrets are injected at deployment time from the environment's secret mechanism and never stored in Git.
- Kubernetes RBAC is least privilege. The serving API needs model-artifact access, not cluster-admin access.
- Logs, traces, metric labels, and error responses are scrubbed of credentials, authorization headers, and raw customer feedback.

## Planned repository boundaries

The requested top-level layout remains recognizable, with two small production-oriented refinements:

```text
app/                         online API, inference, telemetry
training/                    dataset, train, evaluate, registry, governance
tests/                       unit and API/integration tests
load_testing/                Locust scenarios
k8s/base/                    reusable workload manifests
k8s/overlays/local/          local Kubernetes configuration
k8s/overlays/aws/            production configuration references
monitoring/                  Prometheus, Grafana, Loki, Tempo/OTel config
terraform/                   AWS infrastructure and IAM modules
.github/workflows/            CI and protected CD workflows
```

The apparent spaces in the last two paths are typographical only; the implementation paths will be `tests/` and `terraform/`.

The first implementation checkpoint will add the reproducible IMDb dataset pipeline and its configuration. No training or serving code is part of this architecture checkpoint.
