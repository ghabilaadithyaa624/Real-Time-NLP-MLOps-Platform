data "aws_iam_policy_document" "model_artifacts_assume_role" {
  statement {
    sid     = "EksServiceAccount"
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [module.eks.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(module.eks.oidc_provider, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(module.eks.oidc_provider, "https://", "")}:sub"
      values = [
        "system:serviceaccount:${var.kubernetes_namespace}:${var.kubernetes_service_account}"
      ]
    }
  }
}

resource "aws_iam_role" "model_artifacts" {
  name               = "${var.project_name}-${var.environment}-model-artifacts"
  assume_role_policy = data.aws_iam_policy_document.model_artifacts_assume_role.json
}

data "aws_iam_policy_document" "model_artifacts" {
  statement {
    sid       = "ListModelPrefix"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.artifacts.arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${var.model_artifact_prefix}*"]
    }
  }

  statement {
    sid       = "ReadModelObjects"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = ["${aws_s3_bucket.artifacts.arn}/${var.model_artifact_prefix}*"]
  }

  statement {
    sid       = "DecryptModelObjects"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [local.artifacts_kms_key_arn]
  }
}

resource "aws_iam_role_policy" "model_artifacts" {
  name   = "${var.project_name}-${var.environment}-model-artifacts-read"
  role   = aws_iam_role.model_artifacts.id
  policy = data.aws_iam_policy_document.model_artifacts.json
}
