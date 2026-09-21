variable "aws_region" {
  description = "AWS region for the platform resources."
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Short project name used in resource names and tags."
  type        = string
  default     = "customer-feedback"

  validation {
    condition     = can(regex("^[a-z0-9-]{3,24}$", var.project_name))
    error_message = "project_name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "production"

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production."
  }
}

variable "vpc_cidr" {
  description = "CIDR range for the platform VPC."
  type        = string
  default     = "10.40.0.0/16"
}

variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
  default     = "customer-feedback"
}

variable "cluster_version" {
  description = "EKS Kubernetes version."
  type        = string
  default     = "1.31"
}

variable "cluster_endpoint_public_access" {
  description = "Whether the EKS Kubernetes API endpoint is publicly reachable. Prefer false with a private runner or VPN."
  type        = bool
  default     = false
}

variable "cluster_endpoint_public_access_cidrs" {
  description = "CIDRs allowed to reach a public EKS API endpoint. Never use 0.0.0.0/0."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for cidr in var.cluster_endpoint_public_access_cidrs : cidr != "0.0.0.0/0"])
    error_message = "Public EKS access must not allow 0.0.0.0/0."
  }
}

variable "cluster_admin_role_arn" {
  description = "Optional IAM role ARN granted EKS cluster-admin access through an EKS access entry."
  type        = string
  default     = null
}

variable "node_instance_types" {
  description = "On-demand EKS node instance types for CPU inference workloads."
  type        = list(string)
  default     = ["m6i.large"]
}

variable "node_min_size" {
  description = "Minimum EKS node count."
  type        = number
  default     = 2
}

variable "node_desired_size" {
  description = "Desired EKS node count."
  type        = number
  default     = 3
}

variable "node_max_size" {
  description = "Maximum EKS node count."
  type        = number
  default     = 6
}

variable "artifacts_bucket_name" {
  description = "Optional globally unique S3 bucket name. A random suffix is used when null."
  type        = string
  default     = null
}

variable "artifacts_kms_key_arn" {
  description = "Optional existing KMS key ARN for model artifacts. A dedicated key is created when null."
  type        = string
  default     = null
}

variable "db_name" {
  description = "MLflow PostgreSQL database name."
  type        = string
  default     = "mlflow"
}

variable "db_username" {
  description = "MLflow PostgreSQL master username. The password is generated and managed by RDS Secrets Manager."
  type        = string
  default     = "mlflow_admin"

  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9_]{0,62}$", var.db_username))
    error_message = "db_username must be a valid PostgreSQL identifier."
  }
}

variable "db_instance_class" {
  description = "RDS instance class for the MLflow metadata database."
  type        = string
  default     = "db.t4g.medium"
}

variable "db_engine_version" {
  description = "PostgreSQL engine version supported in the selected AWS region."
  type        = string
  default     = "16.4"
}

variable "db_multi_az" {
  description = "Whether RDS should use a Multi-AZ standby."
  type        = bool
  default     = true
}

variable "db_backup_retention_days" {
  description = "RDS automated backup retention period."
  type        = number
  default     = 7
}

variable "kubernetes_namespace" {
  description = "Namespace containing the serving API ServiceAccount."
  type        = string
  default     = "customer-feedback"
}

variable "kubernetes_service_account" {
  description = "Serving API ServiceAccount receiving model artifact access."
  type        = string
  default     = "feedback-api"
}

variable "model_artifact_prefix" {
  description = "S3 prefix that the serving role may read."
  type        = string
  default     = "models/"
}
