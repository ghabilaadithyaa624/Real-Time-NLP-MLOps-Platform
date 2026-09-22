# Real-Time NLP MLOps Platform

[![CI](https://github.com/ghabilaadithyaa624/Real-Time-NLP-MLOps-Platform/actions/workflows/ci.yml/badge.svg)](https://github.com/ghabilaadithyaa624/Real-Time-NLP-MLOps-Platform/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Transformers](https://img.shields.io/badge/🤗%20Transformers-4.48+-yellow.svg)](https://huggingface.co/docs/transformers)
[![MLflow](https://img.shields.io/badge/MLflow-2.19+-0194E2.svg)](https://mlflow.org/)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-EKS%20%7C%20Local-326CE5.svg)](https://kubernetes.io/)

A production-grade, end-to-end MLOps platform engineered for low-latency, real-time Natural Language Processing (NLP) customer feedback classification. It strictly separates the **online serving plane** from the **offline ML lifecycle plane**, ensuring resilient, auditable, and automated model delivery from dataset ingestion to Kubernetes deployment.

---

## 📌 Project Scope & Architecture

### 1. Online Serving Plane (Inference API)
- **Framework**: High-performance asynchronous FastAPI API packaged in hardened, non-root, read-only Docker containers.
- **In-Memory Transformers**: Pinned sequence-classification model (DistilBERT by default) loaded at container startup (`load once, infer many times`).
- **Low Latency & High Concurrency**: Deterministic tokenization, truncation, attention masking, and batching via PyTorch `torch.inference_mode`.
- **Contract & Validation**: Strict Pydantic models rejecting invalid, malicious, empty, or oversized payloads with sanitization.
- **Security & Hardening**:
  - Optional Bearer Token Authentication.
  - Security headers middleware (CSP, HSTS, X-Frame-Options, X-Content-Type-Options).
  - PII Protection: Telemetry, logs, and traces record request/model metadata only—**never raw customer text**.

### 2. Offline ML Lifecycle Plane
- **Dataset Management**: Deterministic dataset ingestion and split validation (IMDb dataset with pinned Hugging Face revisions).
- **Model Training**: PyTorch / Hugging Face Transformers fine-tuning pipeline with reproducible seeds, learning rate schedulers, and early stopping.
- **Evaluation & Model Quality**: Accuracy, F1-score, Precision, Recall, ROC-AUC, latency profiling, and confusion matrices.
- **Model Governance & Registry**:
  - Automated threshold gates for promotion (checks minimum accuracy/F1 before registration).
  - Versioned model artifacts stored securely in S3 / MinIO.
  - MLflow Model Registry tracking with explicit `production` alias promotion.
  - Automated Model Card generation for full auditability and compliance.

### 3. Full-Stack Observability (The LGTM / Prometheus Stack)
- **Metrics**: Prometheus metrics exposition (`/metrics`) tracking request counts, HTTP status codes, latency histograms, inference durations, and token lengths.
- **Logging**: Structured JSON logging correlated with request IDs and trace contexts for Grafana Loki / Promtail.
- **Distributed Tracing**: OpenTelemetry instrumentation with OTLP exporter into Grafana Tempo.
- **Dashboards**: Pre-provisioned Grafana dashboards for customer feedback classification metrics, SLOs, error budgets, and system health.

### 4. Cloud Infrastructure & GitOps Deployment
- **Terraform (AWS)**: Complete Infrastructure as Code for VPC, private subnets, NAT Gateways, EKS cluster, ECR registries, RDS PostgreSQL (MLflow backend), S3 buckets (artifacts), KMS encryption keys, and AWS WAF.
- **Kubernetes (K8s)**:
  - Base manifests: `Deployment`, `Service`, `HPA` (Horizontal Pod Autoscaler), `PDB` (Pod Disruption Budget), `ConfigMap`, `ServiceAccount`.
  - Kustomize overlays for `local` (Minikube / Kind) and `aws` (EKS + Ingress Controller + AWS IAM Roles for Service Accounts - IRSA).
- **Load Testing**: Automated load testing suite using Locust with strict threshold assertions (p95 latency, error rates, throughput).
- **CI/CD Pipelines**: GitHub Actions workflows for continuous integration (linting, Bandit security scanning, unit & integration tests, Docker builds) and automated semantic releases.

---

## 🚀 System Flow Diagram

```text
                                Offline ML Lifecycle
 [Pinned Dataset] ---> [Deterministic Preprocessing] ---> [Transformer Fine-Tuning]
                                                                  |
                                                                  v
 [MLflow Registry] <--- [Governance Threshold Gate] <--- [Evaluation & Metrics]
  (Alias: @production)
        |
        v (Startup-only Resolution)
=================================================================================
                                Online Serving Plane
  [Client] ---> [Kubernetes Ingress / TLS]
                     |
                     v
             [FastAPI Pods]  (In-Memory Transformer, No-Grad Inference)
                     |
        +------------+------------+
        |            |            |
     [Metrics]    [Logs]       [Traces]
        |            |            |
   [Prometheus]   [Loki]       [Tempo]
        \            |            /
         ---> [Grafana Dashboard] <---
```

---

## 🛠️ Quickstart: Running the Project Locally

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or standard `pip` + `venv`
- Docker & Docker Compose (optional for full stack)

### 1. Environment Setup
```powershell
# Using uv (fastest)
uv venv .venv --python 3.11
.\.venv\Scripts\activate
uv pip install -r requirements-dev.txt

# Or using standard pip
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
```

### 2. Run the Full Test Suite
The project comes with 78 unit, integration, security, and configuration tests:
```powershell
pytest -q tests
```

### 3. Run the Inference API Locally
To start the API in local development mode using a local checkpoint:
```powershell
# Set environment variables
$env:MODEL_SOURCE="local"
$env:MODEL_PATH="artifacts/local_model"
$env:MODEL_VERSION="v1.0.0-demo"

# Start Uvicorn
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 4. Test API Endpoints
- **Liveness probe**: `GET http://127.0.0.1:8000/health`
- **Readiness probe**: `GET http://127.0.0.1:8000/health/ready`
- **Model details**: `GET http://127.0.0.1:8000/model`
- **Prometheus metrics**: `GET http://127.0.0.1:8000/metrics`
- **Inference prediction**:
  ```powershell
  Invoke-RestMethod -Uri http://127.0.0.1:8000/predict `
    -Method Post `
    -ContentType "application/json" `
    -Body '{"text": "The service was fast and the experience was exceptional!"}'
  ```

---

## 🐳 Running with Docker Compose

To spin up the entire platform locally (FastAPI + MLflow + PostgreSQL + MinIO + Prometheus + Grafana + Loki + Tempo):
```bash
docker compose --profile mlflow --profile monitoring up --build
```
- **API**: [http://localhost:8000](http://localhost:8000)
- **MLflow UI**: [http://localhost:5000](http://localhost:5000)
- **MinIO Console**: [http://localhost:9001](http://localhost:9001)
- **Prometheus**: [http://localhost:9090](http://localhost:9090)
- **Grafana**: [http://localhost:3000](http://localhost:3000) (Default login: `admin` / `admin`)

---

## 📂 Repository Structure

```text
├── app/                       # Online Serving Plane (FastAPI application)
│   ├── inference/             # Model loading, tokenizer, preprocessing, predictor
│   ├── monitoring/            # Prometheus metrics registry and custom collectors
│   ├── observability/         # Structured JSON logging and OpenTelemetry tracing
│   ├── routes/                # API route handlers (/predict, /health, /model, /metrics)
│   ├── schemas/               # Pydantic request/response data contracts
│   ├── security/              # Bearer auth, security headers, token verification
│   └── main.py                # FastAPI app initialization and lifespan manager
├── training/                  # Offline ML Lifecycle Plane
│   ├── config.py & .yaml      # Hyperparameters, model architecture, training configuration
│   ├── dataset.py             # Deterministic data loading and validation
│   ├── train.py               # Hugging Face Transformer fine-tuning script
│   ├── evaluate.py            # Model evaluation, latency benchmarking, metrics
│   ├── governance.py          # Quality threshold gates and Model Card generation
│   ├── register_model.py      # MLflow model registration
│   └── promote_model.py       # Audited alias-based model promotion (@production)
├── k8s/                       # Kubernetes manifests (Base + AWS & Local overlays)
├── terraform/                 # AWS Infrastructure as Code (EKS, VPC, RDS, S3, KMS, WAF)
├── monitoring/                # Prometheus, Loki, Promtail, Tempo & Grafana configurations
├── load_testing/              # Locust load-testing scenarios & threshold checks
├── docs/                      # Comprehensive technical architecture & operations guides
└── tests/                     # 78 automated test suites covering all platform layers
```

---

## 📄 License
This project is licensed under the Apache-2.0 License.
