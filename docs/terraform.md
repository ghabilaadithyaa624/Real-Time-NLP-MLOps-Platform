# Terraform AWS infrastructure

The Terraform root in `terraform/aws/` owns the cloud infrastructure boundary
for the platform. Kubernetes manifests remain in `k8s/` and are deployed by
the protected release workflow.

## Managed resources

```text
VPC, public/private/database subnets, NAT gateways
EKS cluster and managed inference node group
ECR repository with immutable tags and scan-on-push
KMS key and encrypted/versioned S3 MLflow artifact bucket
Private encrypted RDS PostgreSQL MLflow metadata database
EKS OIDC workload identity role for feedback-api
RDS security group limited to EKS node security group
```

The MLflow database is PostgreSQL on RDS. S3 is only for MLflow artifacts and
model files. S3 is never used as the MLflow metadata database.

## State

Terraform state must use an encrypted remote S3 backend with a DynamoDB lock
table. Copy and customize the example only in an environment-specific working
copy:

```bash
cd terraform/aws
cp backend.tf.example backend.tf
cp terraform.tfvars.example terraform.tfvars
```

Both files are ignored by Git. Do not store credentials in either file.

## Review workflow

Run in a Terraform-enabled environment with AWS credentials supplied through
an approved short-lived identity:

```bash
cd terraform/aws
terraform fmt -check -recursive
terraform init
terraform validate
terraform plan -var-file=terraform.tfvars
```

Review the plan for:

- private subnet placement;
- EKS endpoint exposure;
- RDS deletion protection and backup retention;
- S3 public-access blocking and KMS encryption;
- ECR immutable image tags;
- IAM policy scope for model artifacts;
- cluster administrator access entries.

Only an explicitly approved operator or protected infrastructure workflow may
run:

```bash
terraform apply -var-file=terraform.tfvars
```

No Terraform command, AWS API call, plan, or apply was executed in the current
sandbox. Terraform is not installed and no AWS credentials were requested.

## Security decisions

### EKS API endpoint

The API endpoint is private by default. If a controlled public endpoint is
required, set restricted CIDRs explicitly. `0.0.0.0/0` is rejected by variable
validation.

### Database credentials

The RDS master password is generated and managed by RDS Secrets Manager using
`manage_master_user_password = true`. No password is present in Terraform
variables, Kubernetes manifests, GitHub Actions, or Git.

The MLflow server must retrieve that secret through its own approved secret
mechanism. The API does not need the database password because it loads the
registered model through the MLflow serving/registry endpoint.

### Model artifact access

The serving ServiceAccount receives an IAM role through EKS workload identity.
The role can list the artifact bucket's configured model prefix, read model
objects below that prefix, and decrypt objects with the artifact KMS key.

The role does not receive broad S3, IAM, EKS, or administrator permissions.

## Common errors

### `terraform init` cannot download modules

Verify outbound access to the Terraform Registry and use the exact module
versions declared in the `.tf` files. Do not remove version constraints.

### EKS access is unavailable from CI

The default cluster endpoint is private. Use a self-hosted runner in the VPC,
VPN connectivity, or explicitly review a restricted public endpoint CIDR.

### RDS cannot be reached

The MLflow service must run in the VPC and its security group must be allowed
to reach port 5432. The RDS instance is intentionally not publicly accessible.

### Model downloads fail

Verify the EKS workload identity role, S3 prefix, KMS permissions, and MLflow
artifact configuration. Do not add static AWS keys to the pod.
