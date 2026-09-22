resource "aws_kms_key" "artifacts" {
  count = var.artifacts_kms_key_arn == null ? 1 : 0

  description             = "KMS key for ${var.project_name} MLflow artifacts"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_alias" "artifacts" {
  count = var.artifacts_kms_key_arn == null ? 1 : 0

  name          = "alias/${var.project_name}-${var.environment}-artifacts"
  target_key_id = aws_kms_key.artifacts[0].key_id
}

locals {
  artifacts_kms_key_arn = var.artifacts_kms_key_arn != null ? var.artifacts_kms_key_arn : aws_kms_key.artifacts[0].arn
}
