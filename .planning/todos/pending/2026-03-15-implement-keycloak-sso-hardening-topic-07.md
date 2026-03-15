---
created: 2026-03-15T06:51:58.504Z
title: "Implement Keycloak SSO Hardening (Topic #07)"
area: auth
priority: high
target: v1.4-foundation
effort: 3 weeks
existing_code: 20%
depends_on: []
design_doc: docs/enhancement/topics/07-keycloak-sso-hardening/00-specification.md
files:
  - backend/security/jwt.py
  - backend/security/keycloak_client.py
  - backend/api/routes/health.py
---

## Problem

Keycloak integration has basic JWT validation and JWKS caching, but lacks production-grade resilience patterns. No circuit breaker, no health categorization beyond basic "ok", no enhanced error diagnostics for admin troubleshooting.

## What Exists (20%)

- Basic health check endpoint: `/health` returns `{status: "ok", auth: "local+keycloak" | "local-only"}`
- JWKS fetching with 300s cache and thundering herd prevention (`security/jwt.py`)
- Self-signed cert support (`KEYCLOAK_CA_CERT`)
- `fetchWithRetry` in scheduler tasks (Celery `@retry`)

## What's Needed

- **Circuit breaker pattern** — fail fast when Keycloak is down, avoid cascading failures
- **Health categorization** — classify errors (cert/config/unreachable/timeout) instead of generic "error"
- **Enhanced error diagnostics** — user-facing error messages for common SSO failures
- **Admin health dashboard** — dedicated UI showing Keycloak connection status and history
- **Configuration validation** — pre-flight testing before saving Keycloak config changes
- **Admin notification system** — alert admins when Keycloak becomes unavailable

## Solution

Follow specification at `docs/enhancement/topics/07-keycloak-sso-hardening/00-specification.md`.
