output "vpc_id" {
  description = "VPC ID for the platform."
  value       = module.vpc.vpc_id
}

output "eks_cluster_name" {
  description = "EKS cluster name used by the release workflow."
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "EKS API endpoint."
  value       = module.eks.cluster_endpoint
}

output "ecr_repository_url" {
  description = "Immutable ECR repository URL for the serving image."
  value       = aws_ecr_repository.api.repository_url
}

output "artifacts_bucket_name" {
  description = "S3 bucket holding MLflow artifacts and model files."
  value       = aws_s3_bucket.artifacts.bucket
}

output "artifacts_kms_key_arn" {
  description = "KMS key used for S3 artifact encryption."
  value       = local.artifacts_kms_key_arn
}

output "model_artifacts_role_arn" {
  description = "IAM role ARN for the feedback-api Kubernetes ServiceAccount."
  value       = aws_iam_role.model_artifacts.arn
}

output "api_waf_web_acl_arn" {
  description = "Regional WAF Web ACL ARN to associate with the API ALB."
  value       = try(aws_wafv2_web_acl.api[0].arn, null)
}

output "mlflow_database_endpoint" {
  description = "Private RDS endpoint for the MLflow metadata service."
  value       = aws_db_instance.mlflow.address
}

output "mlflow_database_secret_arn" {
  description = "Secrets Manager ARN containing the RDS-generated master password."
  value       = try(aws_db_instance.mlflow.master_user_secret[0].secret_arn, null)
  sensitive   = true
}
