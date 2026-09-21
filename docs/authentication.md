# Optional API bearer authentication

## Modes

The API supports two explicit modes:

```text
API_AUTH_MODE=disabled
API_AUTH_MODE=bearer
```

The default is `disabled` for local development. In bearer mode, all
application routes require:

```text
Authorization: Bearer <runtime-token>
```

The health and readiness routes remain unauthenticated so Kubernetes and load
balancers can perform probes:

```text
GET /health
GET /health/ready
```

Metrics and model metadata are protected when bearer mode is enabled.

## Runtime configuration

Never commit the token. Supply it through a runtime secret mechanism:

```bash
API_AUTH_MODE=bearer \
API_AUTH_TOKEN='<runtime-token>' \
  docker compose up
```

The Kubernetes manifests intentionally do not contain an API token or Secret
value. If this mode is required in Kubernetes, inject `API_AUTH_TOKEN` from the
cluster's approved secret mechanism and set `API_AUTH_MODE=bearer` through an
environment-specific overlay.

An unset token in bearer mode fails closed with HTTP 503 and does not expose
configuration details.

## Preferred production boundary

For internet-facing production traffic, prefer:

```text
AWS ALB OIDC/Cognito or API gateway authentication
AWS WAF rate limiting
FastAPI application
```

The application bearer mode is useful for controlled internal deployments,
local integration tests, or a deliberately simple trusted boundary. It is not
a replacement for an enterprise identity provider, token rotation, user
identity, authorization scopes, or revocation.

## Error behavior

Invalid or missing credentials receive:

```text
HTTP 401
WWW-Authenticate: Bearer
{"detail":"authentication required"}
```

Missing server-side token configuration receives:

```text
HTTP 503
{"detail":"authentication is not configured"}
```

Invalid mode configuration receives a generic HTTP 503 response. Tokens are
compared with a constant-time comparison and are never logged, traced, placed
in metric labels, or returned in errors.
