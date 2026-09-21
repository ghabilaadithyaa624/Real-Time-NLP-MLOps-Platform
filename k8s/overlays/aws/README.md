# AWS overlay

This overlay is intentionally not deployable until the environment-specific
placeholders are replaced:

```text
REPLACE_WITH_ECR_REGISTRY
REPLACE_WITH_GIT_SHA
REPLACE_WITH_MLFLOW_TRACKING_URI
REPLACE_WITH_IAM_ROLE_ARN
REPLACE_WITH_ACM_CERTIFICATE_ARN
REPLACE_WITH_WAF_ACL_ARN
REPLACE_WITH_API_HOSTNAME
```

The IAM role must be narrowly scoped to the model artifact access required by
the serving process. Do not put AWS access keys in a Secret, ConfigMap, image,
or Deployment environment variable. Use EKS Pod Identity or IRSA.

The AWS overlay assumes that an OpenTelemetry Collector is available in the
`observability` namespace and that its service is named `otel-collector`.
