# CI and release workflows

## CI workflow

`.github/workflows/ci.yml` runs for pull requests and pushes to `main` or
Arena branches. It performs:

```text
Ruff lint
  |
Bandit security scan
  |
Python compilation
  |
pytest unit and integration suite
  |
Docker production-image build without push
```

The CI job has read-only repository permissions. It does not receive AWS
credentials and does not deploy anything.

Run the same validation locally:

```bash
make lint
make security
make compile
make test
```

Or run the complete local CI sequence:

```bash
make ci
```

Expected validation currently includes:

```text
Ruff: all checks passed
Bandit: no medium-or-higher findings
pytest: 49 passed, 1 warning
```

The exact test count can change as new tests are added.

## Release workflow

`.github/workflows/release.yml` is triggered by:

- a version tag matching `v*.*.*`; or
- an explicit `workflow_dispatch` invocation.

It uses a protected GitHub `production` environment and requires:

```text
Secret:
  AWS_DEPLOY_ROLE_ARN

Environment variables:
  AWS_REGION
  ECR_REGISTRY
  ECR_REPOSITORY
  EKS_CLUSTER_NAME
  MLFLOW_TRACKING_URI
  MODEL_ARTIFACT_IAM_ROLE_ARN
  ACM_CERTIFICATE_ARN
  WAF_ACL_ARN
  API_HOSTNAME
```

The release job:

1. authenticates to AWS using GitHub OIDC;
2. logs in to ECR;
3. builds and pushes an image tagged with the Git SHA;
4. configures `kubectl` for EKS;
5. renders the AWS Kustomize overlay;
6. replaces and verifies all environment placeholders;
7. performs a server-side dry run;
8. applies the rendered manifests;
9. waits for the API rollout and availability;
10. smoke-tests `/health` and `/predict`.

The deployed image is tagged with the immutable Git SHA. The release tag is
also pushed as a convenience tag, but Kubernetes is rendered with the SHA
tag.

## OIDC and credential boundary

The workflow requests only:

```yaml
permissions:
  contents: read
  id-token: write
```

No AWS access keys are stored in GitHub Actions variables, repository files,
container images, ConfigMaps, or Kubernetes manifests. The deploy role must
be scoped to the specific ECR, EKS, and manifest operations required by this
workflow.

The model artifact IAM role is a separate value used by the API's Kubernetes
ServiceAccount. It should be scoped to the required MLflow/S3 artifact access
and must not be the GitHub deployment role.

## Release prerequisites

The workflow does not create:

- an EKS cluster;
- an ECR repository;
- an MLflow tracking server;
- an S3 bucket;
- an RDS PostgreSQL database;
- an AWS Load Balancer Controller;
- an ACM certificate;
- DNS records;
- an OpenTelemetry Collector.

Those infrastructure dependencies must already exist and be configured in the
protected production environment.

## Common errors

### Missing release configuration

The workflow fails before AWS authentication if a required variable is empty.
Set the missing protected environment variable rather than hardcoding it in the
workflow.

### OIDC access denied

Verify that the AWS role trust policy allows the repository, branch/tag, and
GitHub OIDC subject used by the protected production environment.

### Unresolved Kubernetes placeholder

The render step intentionally fails if any `REPLACE_WITH_` token remains. Do
not bypass this check; replace the value in the protected environment instead.

### Rollout timeout

Inspect:

```bash
kubectl -n customer-feedback get pods
kubectl -n customer-feedback describe pod <pod-name>
kubectl -n customer-feedback logs deployment/feedback-api
```

A model registry failure should keep readiness false. The release workflow
must fail rather than silently serving a fallback model.

## Verification boundary

The workflows and shell commands are committed configuration. GitHub Actions,
ECR, EKS, AWS OIDC, and production smoke tests have not been executed in this
sandbox. A successful local test run does not claim that a release or AWS
deployment succeeded.
