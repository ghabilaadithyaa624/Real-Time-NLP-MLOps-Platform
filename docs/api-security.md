# API response security

## Headers

The FastAPI service adds conservative headers to every response:

```text
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Permissions-Policy: camera=(), microphone=(), geolocation=()
Content-Security-Policy: default-src 'none'; frame-ancestors 'none'
Cache-Control: no-store
```

The API returns JSON and does not serve browser assets. The restrictive
Content Security Policy therefore prevents accidental browser embedding and
execution without requiring a frontend policy.

## HSTS

Strict Transport Security is opt-in:

```text
ENABLE_HSTS=true
```

The AWS Kubernetes overlay enables it because HTTPS is terminated at the
production ALB. Local Compose and the local Kubernetes overlay leave it
disabled so HTTP development does not create browser HSTS surprises.

HSTS must only be enabled when every browser-visible route for the hostname is
HTTPS-capable. It does not configure TLS or authenticate clients.

## Authentication and rate limiting

These headers do not authenticate requests. The production boundary remains:

```text
AWS ALB HTTPS
AWS WAF rate limiting and managed rules
approved OIDC/Cognito/API-gateway authentication
FastAPI API
```

Authentication credentials and tokens belong to the environment's secret
mechanism and are not read from committed configuration.

## Verification

Response-header tests verify both modes:

```text
ENABLE_HSTS unset: HSTS absent
ENABLE_HSTS=true: HSTS present with one-year max-age
```

The security middleware does not inspect, log, or add request bodies to
responses or telemetry.
