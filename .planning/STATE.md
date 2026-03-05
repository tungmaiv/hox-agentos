---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Production Readiness & Skill Platform
status: unknown
last_updated: "2026-03-05T05:38:18.441Z"
progress:
  total_phases: 2
  completed_phases: 2
  total_plans: 6
  completed_plans: 6
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-05)

**Core value:** Every Blitz employee gets an intelligent, context-aware assistant that automates their daily work routines and lets them build custom automations without writing code — all within an enterprise-secure, on-premise environment where data never leaves the company.
**Current focus:** v1.3 Phase 16 — Navigation & User Experience (COMPLETE — all 3 plans done)

## Current Position

Phase: 16 of 23 (Navigation & User Experience) — COMPLETE
Plan: 03 of 03 complete
Status: Phase 16 complete — all 3 plans done (16-01 backend prefs, 16-02 NavRail, 16-03 profile page)
Last activity: 2026-03-05 - Completed quick task 4: fix avatar dropdown z-index in nav-rail.tsx (z-40 → z-50)

Progress: [###░░░░░░░] ~21%

## Performance Metrics

**Cumulative (v1.0-v1.2):**
- Total plans completed: 54 (across 3 milestones, 18 phases)
- Total timeline: 9 days (2026-02-24 to 2026-03-04)
- Tests: 719 passing (at v1.2 ship)

**v1.3:**
- Plans completed: 6 (15-01, 15-02, 15-03, 16-01, 16-02, 16-03)
- Phases: 9 (15-23)
- Phase 15 complete: AUTH-01, AUTH-05, AUTH-06 satisfied (plan 03); all Phase 15 UAT gaps closed
- Phase 16 complete: 16-01 (user preferences backend: NAV-07, NAV-08, NAV-10); 16-02 (NavRail + route group: NAV-01, NAV-02, NAV-03, NAV-04); 16-03 (profile page + agent injection: NAV-05, NAV-06, NAV-09)

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
v1.2 decisions archived to `.planning/milestones/v1.2-ROADMAP.md`.

v1.3 roadmap decisions:
- [roadmap]: Two-track structure — foundations (15-18) then skill platform (19-23)
- [roadmap]: Phase 17 (performance) architecturally independent of Phase 16 — can parallelize if needed
- [roadmap]: Phase 21 (security hardening) depends on both Phase 19 and Phase 20
- [15-01]: Allowlist middleware approach — all routes protected by default, public routes explicitly listed
- [15-01]: Use getToken() from next-auth/jwt (not raw jose) — next-auth v5 encrypts cookie with NEXTAUTH_SECRET
- [15-01]: Admin layout keeps RBAC role check; only auth redirect removed (defense-in-depth)
- [Phase 15]: No confirmation dialog on Sign Out — instant logout for clean UX per user preference
- [Phase 15]: Keycloak end-session uses id_token_hint — required for proper Keycloak SSO session termination
- [Phase 15]: refetchOnWindowFocus over BroadcastChannel — built-in next-auth, simpler for 100-user scale
- [Phase 15]: Pass explicit secret to getToken() in middleware — @auth/core 0.41.0 does not auto-detect NEXTAUTH_SECRET unlike next-auth v4
- [Phase 15]: AuthErrorToasts must be inside SessionProvider — useSession() requires SessionProvider ancestor to detect unauthenticated status transitions
- [Phase 16]: [16-01]: JSONB column uses JSON().with_variant(JSONB(), 'postgresql') for SQLite test compat
- [Phase 16]: [16-01]: get_user_preference_values() helper exported from route module for Plan 03 agent prompt injection
- [Phase 16]: [16-01]: Router prefix /users/me/preferences (plural, RESTful) distinct from legacy /user/instructions
- [Phase 16]: NavRail uses useSession() client-side for role check — avoids prop drilling from server layout
- [Phase 16]: (authenticated) route group layout excludes /login and /api routes — URLs unchanged for all authenticated pages
- [16-03]: Backend change-password endpoint added (auth_local_password.py) — was missing from auth_local.py, required by PasswordChangeCard
- [16-03]: user_prefs loaded in same async_session block as custom_instructions in _master_node — no extra DB round-trip
- [16-03]: concise response style gets no extra directive — base master_agent prompt is already concise

### Pending Todos

- [ ] Start WhatsApp Business API verification process (takes 1-4 weeks, needed for future live testing)
- [ ] Add CREDENTIAL_ENCRYPTION_KEY to production .env before OAuth flows (deferred to v1.4)
- [ ] [POST-MVP] HashiCorp Vault for secret management
- [ ] [TECH-DEBT] Fix frontend `pnpm build` failure — SWR hooks in Server Components cause prerender crash on `/settings/integrations` and `/settings/memory` pages. Root cause: `useSWR()` destructuring (`const { data } = useSWR(...)`) runs during static export where SWR context is undefined. Fix: add `"use client"` directive to affected pages, or move SWR calls into client sub-components.
- [ ] [TECH-DEBT] Keycloak SSO login returns "Server error — Configuration" (`/api/auth/error?error=Configuration`). next-auth Keycloak provider fails during OIDC discovery or token exchange. Likely causes: (1) `KEYCLOAK_ISSUER` URL unreachable from Next.js server (self-signed cert / DNS), (2) `KEYCLOAK_CLIENT_ID` or `KEYCLOAK_CLIENT_SECRET` mismatch with Keycloak realm config, (3) Keycloak service not running or realm not configured. Investigate in Phase 18 (Identity Configuration) or fix earlier if blocking dev workflows.

### Blockers/Concerns

- CVE-2025-29927: Next.js must be confirmed at 15.2.3+ before any middleware.ts is written (Phase 15)
- Embedding sidecar dual-load risk: FlagEmbedding removal must be atomic with sidecar addition (Phase 17)
- Keycloak optional boot: config.py validation must handle missing keycloak_url gracefully (Phase 18)

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 4 | fix avatar dropdown z-index in nav-rail.tsx (z-40 → z-50) | 2026-03-05 | 8a45435 | [4-fix-avatar-dropdown-z-index-in-nav-rail-](./quick/4-fix-avatar-dropdown-z-index-in-nav-rail-/) |

## Session Continuity

Last session: 2026-03-05
Stopped at: Completed 16-03-PLAN.md (Profile page + settings slimdown + agent preference injection)
Resume file: .planning/phases/16-navigation-user-experience/16-CONTEXT.md
