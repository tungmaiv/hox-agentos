---
created: 2026-03-06T18:08:37.329Z
title: Investigate slow page load and signin performance
area: auth
files:
  - frontend/src/app/api/copilotkit/route.ts
  - frontend/src/app/page.tsx
  - backend/security/keycloak_config.py
  - backend/security/jwt.py
---

## Problem

Sign-in took ~5 minutes to complete (unacceptable — should be under 3 seconds).
Page loading also took multiple seconds to render.

Reported after phase 18 which introduced:
- `KeycloakConfigResolver` — reads platform_config from DB on every auth request (before the lock was added, this could have caused thundering herd on startup)
- `get_keycloak_config()` called on each `validate_token()` call (60s TTL cache but cold-start DB read)
- `auth.ts` in Next.js now fetches `/api/internal/keycloak/provider-config` at startup before the server is ready
- Frontend container restart triggered by `_restart_frontend_container` (Docker SDK sync call in BackgroundTask)

Hypotheses:
1. On first request, `get_keycloak_config()` DB read blocks under high concurrency (fixed by lock in this session, but needs verification)
2. `auth.ts` startup fetch to `/api/internal/keycloak/provider-config` fails/times out → NextAuth retries slowly
3. NextAuth session resolution adds latency on every page load (SSR waterfall)
4. Cold-start: LiteLLM proxy or Keycloak not ready when frontend boots → repeated retries
5. JWKS fetch on every cold start (300s TTL — but first request hits network)

## Solution

1. Profile: check backend logs for slow requests (`just logs backend | grep duration_ms`)
2. Check `auth.ts` startup timing — does `/api/internal/keycloak/provider-config` respond fast?
3. Measure: `curl -w "%{time_total}" http://localhost:8000/health` and `http://localhost:8000/api/auth/config`
4. Check if NextAuth is doing multiple round-trips on each page load (network tab)
5. Consider adding startup readiness probe before frontend fetches backend config
6. Consider caching JWKS and keycloak config aggressively on startup (pre-warm on app init)
