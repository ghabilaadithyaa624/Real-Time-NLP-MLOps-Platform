# Kubernetes serving manifests

## Scope

The Kubernetes manifests package the existing FastAPI image as a secure,
readiness-gated serving workload. They do not create AWS infrastructure,
MLflow, PostgreSQL, S3, an OpenTelemetry Collector, or an EKS cluster.
Those dependencies must exist before the production overlay is applied.

```text
k8s/base/                  provider-neutral API workload
k8s/overlays/local/        local model PVC and one-replica configuration
k8s/overlays/aws/          ECR, MLflow, IAM, ALB placeholders
```

## Base workload properties

The base deployment provides:

- non-root UID/GID `10001`;
- `RuntimeDefault` seccomp profile;
- dropped Linux capabilities;
- disabled privilege escalation;
- read-only root filesystem;
- memory-backed writable `/tmp` only;
- CPU and memory requests/limits;
- startup, liveness, and readiness probes;
- rolling updates with `maxUnavailable: 0`;
- pod anti-affinity and topology spreading;
- a PodDisruptionBudget;
- CPU and memory HPA targets;
- Prometheus scrape annotations;
- no mounted service-account token by default.

Readiness calls `/health/ready`, so a pod cannot receive traffic until the
configured model has loaded successfully. Liveness calls `/health` and does
not require the model registry to be available.

## Local overlay

Build the image first in a Docker-enabled environment:

```bash
docker build --tag real-time-nlp-api:local .
```

Create the local namespace and model volume:

```bash
kubectl apply -k k8s/overlays/local
```

The local overlay expects the `feedback-api-model` PVC to contain a Hugging
Face model checkpoint at `/models/model`. The PVC is deliberately not
populated by the repository. Load the checkpoint using a cluster-appropriate,
reviewed workflow before expecting readiness to become healthy.

Inspect rollout and probes:

```bash
kubectl -n customer-feedback-local rollout status deployment/feedback-api
kubectl -n customer-feedback-local get pods,svc,hpa,pdb
kubectl -n customer-feedback-local port-forward service/feedback-api 8000:80
```

Then verify:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
```

## AWS overlay prerequisites

Before applying the AWS overlay, replace every placeholder in
`k8s/overlays/aws/`:

```text
REPLACE_WITH_ECR_REGISTRY
REPLACE_WITH_GIT_SHA
REPLACE_WITH_MLFLOW_TRACKING_URI
REPLACE_WITH_IAM_ROLE_ARN
REPLACE_WITH_ACM_CERTIFICATE_ARN
REPLACE_WITH_API_HOSTNAME
```

The AWS overlay assumes:

- an existing EKS cluster;
- AWS Load Balancer Controller with an `alb` IngressClass;
- an ECR image built from this Git SHA;
- an MLflow tracking/registry endpoint;
- an OpenTelemetry Collector service at
  `otel-collector.observability.svc.cluster.local:4317`;
- EKS Pod Identity or IRSA for model artifact access;
- a certificate in AWS Certificate Manager;
- DNS for the configured API hostname.

Validate the rendered resources before applying:

```bash
kubectl kustomize k8s/overlays/aws > /tmp/feedback-api-aws.yaml
kubectl apply --dry-run=server -f /tmp/feedback-api-aws.yaml
```

Apply only after the placeholders and cluster prerequisites have been
reviewed:

```bash
kubectl apply -k k8s/overlays/aws
kubectl -n customer-feedback rollout status deployment/feedback-api
kubectl -n customer-feedback get ingress feedback-api
```

These commands are instructions only. No Kubernetes cluster or AWS resource
has been created by this repository change.

## Security boundary

The serving pod does not receive AWS access keys. The AWS service-account
patch enables a workload-identity token because the model artifact path may
require AWS access. Scope the referenced IAM role to the required S3 prefixes
and registry operations only.

Do not put the following in Git:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_SESSION_TOKEN
MLflow passwords
private keys
API tokens
```

Use the cluster secret mechanism or workload identity for credentials that are
actually required by an external dependency.

## Common errors

### Readiness remains 503

Inspect the model-load logs and configuration:

```bash
kubectl -n customer-feedback get pods
kubectl -n customer-feedback logs deployment/feedback-api
kubectl -n customer-feedback describe pod <pod-name>
```

A missing production model, an invalid MLflow URI, or missing workload
identity should leave readiness false rather than loading a fallback model.

### `ImagePullBackOff`

Confirm that the AWS image placeholder was replaced with the ECR registry and
that the node or workload identity can pull the image.

### ALB is not created

Confirm that the AWS Load Balancer Controller is installed, the `alb`
IngressClass exists, and the ACM ARN and hostname placeholders were replaced.

### HPA has no metrics

The cluster must provide the Kubernetes resource metrics API. HPA creation
alone does not install Metrics Server.

### Model PVC is empty locally

The repository creates only the PVC declaration. Copy or restore a reviewed
model checkpoint into the claim through a cluster-specific process.
