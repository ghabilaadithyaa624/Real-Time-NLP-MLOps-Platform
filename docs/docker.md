# Docker containerization

## Image design

```text
Docker build context
  |
  +-- runtime dependency stage
  |     +-- Python virtual environment
  |
  +-- runtime stage
        +-- python:3.11-slim-bookworm
        +-- libgomp1 only
        +-- app source
        +-- non-root user: app
        +-- no credentials
```

The image contains the API runtime only. Training code, tests, documentation, downloaded datasets, local MLflow state, and development environments are excluded through `.dockerignore`.

The container:

- runs as UID/GID 10001;
- binds Uvicorn to `0.0.0.0`;
- uses one worker per container so each replica owns one in-memory model;
- has a healthcheck for `/health`;
- uses no `latest` tag in deployment workflows;
- reads model and MLflow configuration from environment variables;
- does not bake credentials into the image;
- uses a read-only root filesystem in Compose.

## Build

```bash
docker build \
  --tag real-time-nlp-api:local \
  .
```

For a release image, use an immutable version or Git SHA tag:

```bash
docker build \
  --tag real-time-nlp-api:${GIT_SHA} \
  .
```

## Local Compose

The Compose profile uses an explicit local model source. It expects a saved Hugging Face checkpoint at `./artifacts/training` by default:

```bash
docker compose up --build
```

Use a different checkpoint directory without editing the file:

```bash
MODEL_PATH=/absolute/path/to/model \
MODEL_VERSION=local-test \
docker compose up --build
```

The API is available at:

```text
http://localhost:8000
```

The container does not download a model into the image. The model directory is mounted read-only at `/models/model`.

## Verification

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
curl -X POST http://localhost:8000/predict \
  -H 'Content-Type: application/json' \
  -d '{"text":"The product was fantastic."}'
```

A missing local model causes readiness to return HTTP 503; it does not result in a fallback model.

## Production image rules

Production deployment should:

- push the image to ECR;
- tag it with the Git SHA;
- preferably deploy by image digest;
- use an external model registry and artifact store;
- inject secrets at runtime;
- scan the image before deployment;
- run as the non-root `app` user;
- use Kubernetes resource and security constraints.

Docker is not available in the current sandbox, so the Docker build and Compose startup commands must be run in a Docker-enabled environment. The Dockerfile is statically checked by the test suite.
