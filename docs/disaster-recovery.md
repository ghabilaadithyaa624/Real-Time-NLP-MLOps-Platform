# Backup, restore, and disaster recovery

## Scope

The platform has two durable MLOps state boundaries:

```text
RDS PostgreSQL
  MLflow runs, metadata, and model registry state

S3 with versioning and KMS encryption
  MLflow model files, tokenizer files, and evaluation artifacts
```

The API pods and local Kubernetes model PVC are not the system of record for
model artifacts. A new serving deployment must be able to reload the approved
model from MLflow and S3.

This document is an operational runbook and recovery target. No backup,
restore, or disaster-recovery exercise has been executed by this repository
phase.

## Recovery objectives

These are provisional operational targets requiring environment approval and
testing:

```text
MLflow metadata RPO: up to the configured RDS backup interval
MLflow metadata RTO: 60 minutes
Model artifact RPO: versioned S3 objects within the surviving AWS region
Serving RTO: 30 minutes after infrastructure and registry availability
```

The targets are not measured results. A real drill must record the timestamp,
backup identifier, restore duration, model version, alias state, and smoke-test
result.

## Preventive configuration

Terraform configures:

```text
RDS Multi-AZ: enabled by default
RDS automated backups: 7 days by default
RDS deletion protection: enabled
RDS storage encryption: enabled
S3 versioning: enabled
S3 public access: blocked
S3 KMS encryption: enabled
```

The retention period is configurable from 1 to 35 days. Production changes
must be reviewed because a shorter retention period changes the recovery point
objective.

## RDS metadata backup

Inspect the instance without printing credentials:

```bash
aws rds describe-db-instances \
  --db-instance-identifier customer-feedback-production-mlflow \
  --query 'DBInstances[0].{Status:DBInstanceStatus,Endpoint:Endpoint.Address,BackupRetention:BackupRetentionPeriod,MultiAZ:MultiAZ}'
```

Create an operator-approved manual snapshot:

```bash
aws rds create-db-snapshot \
  --db-instance-identifier customer-feedback-production-mlflow \
  --db-snapshot-identifier customer-feedback-production-mlflow-<utc-timestamp>
```

Wait for completion:

```bash
aws rds wait db-snapshot-available \
  --db-snapshot-identifier customer-feedback-production-mlflow-<utc-timestamp>
```

Do not place the RDS password in shell history or command arguments. RDS
manages the master password through Secrets Manager.

## RDS restore

1. Confirm the incident and select an approved snapshot.
2. Restore to a new private RDS instance rather than overwriting the source:

   ```bash
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier customer-feedback-production-mlflow-restore \
     --db-snapshot-identifier <approved-snapshot-id> \
     --db-instance-class db.t4g.medium \
     --db-subnet-group-name customer-feedback-production-mlflow \
     --vpc-security-group-ids <mlflow-db-security-group-id> \
     --no-publicly-accessible
   ```

3. Confirm encryption, private routing, backup retention, and security-group
   membership before allowing MLflow to connect.
4. Restore or rotate the MLflow database secret through the approved secret
   mechanism.
5. Point the MLflow service at the restored endpoint.
6. Verify the registry model and aliases before re-admitting API traffic.

Do not run a restore directly against production without an approved change
window and rollback plan.

## S3 artifact recovery

List object versions without downloading customer data:

```bash
aws s3api list-object-versions \
  --bucket <artifacts-bucket> \
  --prefix models/
```

Restore a reviewed object version to a temporary recovery key:

```bash
aws s3api copy-object \
  --bucket <artifacts-bucket> \
  --copy-source <artifacts-bucket>/models/<object-key>?versionId=<version-id> \
  --key recovery/<incident-id>/<object-key> \
  --server-side-encryption aws:kms \
  --ssekms-key-id <artifacts-kms-key-arn>
```

Validate the recovered model through MLflow before changing any alias. Do not
point the production alias at an artifact that has not passed the existing
evaluation and governance process.

## MLflow registry verification

After restoring MLflow, verify the registry endpoint and alias state:

```bash
curl --fail "$MLFLOW_TRACKING_URI/version"
```

Use the MLflow client or approved registry tooling to confirm:

```text
customer-feedback-classifier exists
production alias exists
production alias points to an intended READY version
validated metadata and evaluation hash are present
artifact URI is reachable
```

The API should remain unready until the configured production alias can be
loaded and warmed successfully.

## Serving recovery

After infrastructure or registry recovery:

```bash
kubectl -n customer-feedback rollout restart deployment/feedback-api
kubectl -n customer-feedback rollout status deployment/feedback-api --timeout=10m
kubectl -n customer-feedback get pods
```

Verify the health contract:

```bash
kubectl -n customer-feedback port-forward service/feedback-api 8000:80
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/health/ready
curl --fail http://localhost:8000/model
```

Run the approved synthetic smoke test only after readiness succeeds. Record
the request timestamp, response status, model version, and deployment image
SHA without storing customer text.

## Disaster-recovery drill checklist

```text
[ ] Incident and change window approved
[ ] Last known-good RDS snapshot identified
[ ] Artifact bucket and KMS key available
[ ] Restore target created in private subnets
[ ] MLflow secret retrieved through approved mechanism
[ ] MLflow endpoint responds
[ ] Model registry and production alias verified
[ ] Artifact URI read succeeds
[ ] API rollout completes
[ ] /health and /health/ready return expected responses
[ ] /model reports the intended model version
[ ] Synthetic prediction smoke test passes
[ ] DNS/ALB traffic re-admitted
[ ] Recovery duration and RPO recorded
[ ] Temporary restore resources cleaned up
```

## Credential and privacy boundary

Never put these values in runbooks, commands, GitHub logs, or issue comments:

```text
AWS access keys
RDS passwords
Secrets Manager secret values
API tokens
customer feedback
Authorization headers
```

Use IAM roles, workload identity, Secrets Manager, and redacted operational
logs. Recovery commands should print resource identifiers and statuses, not
secret material or request bodies.
