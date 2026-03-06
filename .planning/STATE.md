---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Production Readiness & Skill Platform
status: unknown
last_updated: "2026-03-06T09:20:08.965Z"
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 16
  completed_plans: 16
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-05)

**Core value:** Every Blitz employee gets an intelligent, context-aware assistant that automates their daily work routines and lets them build custom automations without writing code — all within an enterprise-secure, on-premise environment where data never leaves the company.
**Current focus:** v1.3 Phase 18 — Identity Configuration (Complete — 3/3 plans done)

## Current Position

Phase: 18 of 23 (Identity Configuration) — Complete
Plan: 03 of 03 complete
Status: Plan 18-03 done — Frontend auth.ts dynamic Keycloak provider + login SSO button + admin Identity tab (IDCFG-03, IDCFG-04, IDCFG-05, IDCFG-08): pnpm build passes
Last activity: 2026-03-06 - Completed 18-03: IDCFG-03, IDCFG-04, IDCFG-05, IDCFG-08 satisfied. Phase 18 complete.

Progress: [########░░] ~55%

## Performance Metrics

**Cumulative (v1.0-v1.2):**
- Total plans completed: 54 (across 3 milestones, 18 phases)
- Total timeline: 9 days (2026-02-24 to 2026-03-04)
- Tests: 719 passing (at v1.2 ship)

**v1.3:**
- Plans completed: 7 (15-01, 15-02, 15-03, 16-01, 16-02, 16-03, 17-01)
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
- [Phase 17]: [17-01]: SidecarEmbeddingProvider falls back to BGE_M3Provider on ConnectError — preserves correctness when sidecar not yet warm
- [Phase 17]: [17-01]: validate_dimension() checks /health at startup — catches EMBEDDING_MODEL misconfiguration early
- [Phase 17]: [17-01]: embedding_model_cache named volume persists bge-m3 download across container restarts
- [Phase 17]: [17-02]: timed() uses finally block — fires even when wrapped block raises, capturing latency up to exception point
- [Phase 17]: [17-02]: canvas_compile wraps builder.set_entry_point() in graphs.py (uncompiled builder is the contract; actual .compile() is caller's job)
- [Phase 17]: [17-02]: channel_delivery wraps per-attempt HTTP send (not retry loop) — captures actual delivery latency not retry overhead
- [Phase 17]: [17-03]: cachetools TTLCache chosen over Redis — in-process cache sufficient at ~100 user scale, no network hop
- [Phase 17]: [17-03]: patch target for get_episode_threshold_cached tests is agents.master_agent.get_episode_threshold_cached (import site), not memory.medium_term (definition site)
- [Phase 17]: [17-03]: _get_episode_threshold() private function removed from master_agent.py — superseded by get_episode_threshold_cached() in memory.medium_term with caching built in
- [Phase 17]: [17-05]: Admin memory reindex uses tool:admin permission — consistent with system_config.py pattern for system-wide admin ops
- [Phase 17]: [17-05]: reindex_memory_task uses separate async_session() per read/write batch — avoids holding transactions during slow embedding calls
- [Phase 17]: [17-05]: Startup sidecar check is non-fatal in main.py lifespan — backend starts even when sidecar not warm
- [Phase 17]: [17-06]: get_session() asynccontextmanager yields contextvar session when set, falls through to async_session() otherwise — single session per HTTP request via RequestSessionMiddleware
- [Phase 17]: [17-06]: Celery scheduler tasks explicitly excluded from migration — they manage own session lifecycle outside HTTP request context
- [Phase 17]: [17-04]: Admin Memory page uses proxy route pattern matching copilotkit/route.ts — auth() from @/auth, accessToken via Record<string,unknown> cast, BACKEND_URL env precedence
- [Phase 17]: [17-07]: asyncio.Lock at module level — matches module-level cache globals it protects; double-checked locking avoids contention on warm cache fast path
- [Phase 17]: [17-07]: useSkills() hoisted to ChatPanel (not layout) — ChatPanel is the correct boundary owning the CopilotKit key= prop and null conversationId early-return
- [Phase 18]: IDCFG-06: platform_config typed columns over system_config key/value — type safety, simpler queries, explicit migration path
- [Phase 18]: [18-01]: KeycloakConfigResolver 60s TTL (vs JWKS 300s) — admin config changes propagate within 1 minute; resolver returns None on DB error (safe local-only fallback)
- [Phase 18]: [18-01]: client_secret encrypted as JSON string (not JSONB) in platform_config — avoids JSONB variant issues across SQLite tests + PostgreSQL prod
- [Phase 18]: [18-02]: GET config returns has_secret: bool only — never raw or masked client_secret string
- [Phase 18]: [18-02]: Internal provider-config endpoint uses X-Internal-Key header (not JWT) — Next.js server-side can't authenticate via JWT before it has credentials
- [Phase 18]: [18-02]: asyncio.to_thread(_restart_frontend_container) — Docker SDK is synchronous, must run in thread to avoid blocking async event loop
- [Phase 18]: [18-03]: Remove explicit providers type annotation from auth.ts — let TypeScript infer, avoids Parameters<typeof NextAuth>[0]['providers'] resolution failure
- [Phase 18]: [18-03]: Identity tab placed between Permissions and Config in ADMIN_TABS — locked by CONTEXT.md decision (IDCFG-04)

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
| Phase 17 P05 | 5 | 5 tasks | 6 files |
| Phase 17 P06 | 6 | 5 tasks | 15 files |
| Phase 17 P04 | 3 | 3 tasks | 3 files |
| Phase 17 P07 | 3 | 4 tasks | 3 files |
| Phase 18 P01 | 27 | 4 tasks | 14 files |
| Phase 18 P02 | 10 | 4 tasks | 4 files |
| Phase 18 P03 | 16 | 4 tasks | 7 files |

## Session Continuity

Last session: 2026-03-06
Stopped at: Completed 18-03-PLAN.md (Frontend auth.ts dynamic Keycloak + admin Identity tab, IDCFG-03, IDCFG-04, IDCFG-05, IDCFG-08) — Phase 18 complete
Resume file: .planning/phases/18-identity-configuration/18-03-SUMMARY.md
