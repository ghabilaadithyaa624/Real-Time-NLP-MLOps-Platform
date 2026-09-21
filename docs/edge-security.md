# Production edge security

## Boundary

The AWS Kubernetes overlay terminates HTTPS at an internal AWS Application Load
Balancer and associates a regional AWS WAF Web ACL:

```text
Client or approved private network
          |
          v
HTTPS ALB
  +-- ACM certificate
  +-- AWS WAF managed common rules
  +-- AWS WAF per-IP rate limit
          |
          v
ClusterIP Service -> FastAPI pods
```

The WAF currently provides filtering and rate limiting. It is not an identity
provider and must not be described as authentication.

## WAF policy

Terraform creates two rules when `waf_enabled = true`:

```text
rate-limit-by-ip
  default: 2,000 requests per five minutes per IP

AWSManagedRulesCommonRuleSet
  AWS-managed common web protections
```

The rate limit is configurable with:

```hcl
waf_rate_limit_per_ip = 2000
```

The allowed range is 100 to 20,000,000 requests per five minutes per IP. Tune
this using measured traffic and an approved abuse-prevention policy. A WAF IP
rate limit is not a replacement for per-user quotas when clients share NAT or
proxy addresses.

## Authentication boundary

The ALB is internal by default. Before exposing it publicly, configure an
approved authentication layer, such as:

- ALB OIDC or Cognito authentication;
- an enterprise API gateway;
- an authenticated service mesh or private network boundary.

The client ID, client secret, issuer configuration, and session settings must
come from the environment's secret mechanism. They are intentionally not
managed as committed Kubernetes manifests or Terraform plaintext variables.

A WAF rate-limit rule does not authenticate callers. A successful WAF request
still requires the configured identity and authorization policy.

## Release integration

The protected GitHub release workflow requires:

```text
WAF_ACL_ARN
```

It replaces `REPLACE_WITH_WAF_ACL_ARN` in the AWS Ingress manifest and fails if
any placeholder remains. The WAF ARN should be the Terraform output:

```text
api_waf_web_acl_arn
```

## Privacy and observability

Do not include customer text, authorization headers, API keys, request IDs, or
session tokens in WAF labels, ALB access-log annotations, Prometheus labels,
Loki labels, or trace attributes. Use approved access-log storage and retention
policies for any ALB/WAF logs.

No public ALB, WAF Web ACL, authentication provider, or AWS resource was
created by this repository phase.
