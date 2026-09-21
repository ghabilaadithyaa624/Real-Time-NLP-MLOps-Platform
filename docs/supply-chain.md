# Container supply-chain controls

## Workflow

The CI workflow now performs the following before a pull request or branch
build can be considered valid:

```text
Build production image locally
        |
        v
Trivy HIGH/CRITICAL scan
        |
        v
CycloneDX image SBOM
        |
        v
Artifact upload
```

The release workflow repeats the Trivy scan and SBOM generation against the
immutable image pushed to ECR before Kubernetes manifests are applied.

## Vulnerability policy

The Trivy gate scans operating-system and library packages for:

```text
HIGH
CRITICAL
```

Unfixed vulnerabilities are ignored by the current gate because upstream
remediation may not yet exist. This is a documented risk decision, not proof
that an image has no vulnerabilities. The scan output must be reviewed and the
base image or dependency upgraded when a fixed remediation becomes available.

A release stops before EKS deployment if the scan exits non-zero.

## SBOM

SBOMs use CycloneDX JSON and are uploaded as workflow artifacts:

```text
sbom-ci-<sha>
sbom-release-<sha>
```

The SBOM records the image dependency inventory for the exact Git SHA. It is a
build artifact, not a substitute for vulnerability triage or license review.

## Immutable image boundary

The release workflow pushes:

```text
<registry>/<repository>:<git-sha>
<registry>/<repository>:<release-tag>
```

ECR is configured with immutable image tags. Kubernetes is rendered with the
Git SHA tag rather than `latest`.

The release also enables BuildKit provenance metadata. Future deployments may
add a separately approved signing and verification policy; this phase does not
claim that images are cryptographically signed or verified at admission.

## Local checks

When Docker is available, reproduce the CI image scan locally:

```bash
docker build --tag real-time-nlp-api:local .
trivy image \
  --ignore-unfixed \
  --vuln-type os,library \
  --severity HIGH,CRITICAL \
  real-time-nlp-api:local
```

Generate a local SBOM with Syft:

```bash
syft real-time-nlp-api:local \
  --output cyclonedx-json=sbom-local.cdx.json
```

Do not commit local SBOMs or scan output unless the repository's artifact
retention process explicitly requires it.

## Verification boundary

The workflow definitions and action versions are statically checked in this
repository. Docker, Trivy, Syft, GitHub Actions, ECR, and release scans have
not been executed in the current sandbox.
