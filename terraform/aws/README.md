# AWS Terraform root

This directory defines the AWS infrastructure boundary for the platform. It
is configuration only; it does not prove that an AWS account has been
configured or that resources have been created.

## Managed boundaries

```text
VPC and private subnets
EKS cluster and managed node group
ECR repository with immutable tags and scan-on-push
Encrypted S3 bucket for MLflow artifacts
KMS key for artifact encryption
RDS PostgreSQL for MLflow metadata and registry state
EKS workload identity role for the serving API
Security groups and least-privilege IAM policies
```

The MLflow metadata database is RDS PostgreSQL. S3 is used only for model and
artifact files, never as the MLflow metadata backend.

## State requirements

Use a separately bootstrapped, encrypted S3 state bucket with a DynamoDB lock
table. The example backend is in `backend.tf.example`; it is not active by
default because the state bucket must exist before this root can initialize.

Never commit:

```text
backend.tf
*.tfstate
*.tfstate.*
.terraform/
*.tfvars
```

The committed `terraform.tfvars.example` contains placeholders and safe
non-secret defaults only.

## Review commands

From this directory, in an environment with Terraform and AWS credentials
provided through an approved identity mechanism:

```bash
terraform fmt -check -recursive
terraform init
terraform validate
terraform plan -var-file=terraform.tfvars
```

Review the plan before any apply. For production, use a protected CI role or a
short-lived operator identity and store the plan as a controlled artifact.

No `terraform init`, `terraform validate`, `terraform plan`, or `terraform
apply` command was run in the current sandbox because Terraform is unavailable.
No AWS credentials were requested or stored.

## Security design

- The EKS API endpoint is private by default.
- Public endpoint access requires explicitly supplied CIDRs and rejects
  `0.0.0.0/0`.
- RDS is private, encrypted, non-public, and protected from accidental
  deletion.
- RDS generates and manages the master password in Secrets Manager.
- ECR tags are immutable and images are scanned on push.
- S3 public access is blocked, versioning is enabled, and objects use KMS
  encryption.
- The serving role can read only the configured model artifact prefix.
- The serving pod receives AWS permissions through EKS workload identity, not
  static access keys.
- Cluster administrator access is optional and must be provided as an explicit
  IAM role ARN.
