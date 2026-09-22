variable "waf_rate_limit_per_ip" {
  description = "Requests per five-minute window before AWS WAF blocks an IP."
  type        = number
  default     = 2000

  validation {
    condition     = var.waf_rate_limit_per_ip >= 100 && var.waf_rate_limit_per_ip <= 20000000
    error_message = "waf_rate_limit_per_ip must be between 100 and 20,000,000."
  }
}

variable "waf_enabled" {
  description = "Whether to create the regional WAF Web ACL for the API ALB."
  type        = bool
  default     = true
}

resource "aws_wafv2_web_acl" "api" {
  count = var.waf_enabled ? 1 : 0

  name  = "${var.project_name}-${var.environment}-api"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "rate-limit-by-ip"
    priority = 1

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = var.waf_rate_limit_per_ip
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project_name}-${var.environment}-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "aws-managed-common-rules"
    priority = 10

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.project_name}-${var.environment}-common-rules"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.project_name}-${var.environment}-api"
    sampled_requests_enabled   = true
  }
}
