---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Production Readiness & Skill Platform
status: unknown
last_updated: "2026-03-08T12:34:26.900Z"
progress:
  total_phases: 7
  completed_phases: 6
  total_plans: 26
  completed_plans: 27
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-05)

**Core value:** Every Blitz employee gets an intelligent, context-aware assistant that automates their daily work routines and lets them build custom automations without writing code — all within an enterprise-secure, on-premise environment where data never leaves the company.
**Current focus:** v1.3 Phase 20 — Skill Platform B Discovery & Catalog (Gap closure — 20-06 complete)

## Current Position

Phase: 20 of 23 (Skill Platform B — Discovery & Catalog) — Complete (including gap closure)
Plan: 06 of 06 complete (gap closure plans 20-04, 20-05, 20-06 added post-UAT)
Status: Phase 20 done — FTS GIN index (20-01), /api/skills endpoint with browse/search (20-02), user skills catalog page + admin filter bars (20-03), usage_count increment + skill detail drawer (20-04), usage_count increment in skill executor node (20-05), admin /skills sort fix: disableInternalSort + usageCount field (20-06). SKCAT-01/02/03/04 satisfied.
Last activity: 2026-03-08 - Completed 20-06: Admin /skills sort dropdown fixed — ArtifactTable disableInternalSort prop + SkillDefinition.usageCount field enables Newest/Oldest/Most Used to actually reorder table rows.

Progress: [#########░] ~61%

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
- [Phase 19]: Migration 022 not auto-applied in running container — must `docker cp` new migration files then run `alembic upgrade head` inside container after container-only deploys
- [Phase 19]: source_url not parsed from SKILL.md frontmatter initially — gap found in UAT, fixed with one-line addition; ZIP MANIFEST.json and URL import already worked
- [Phase 19]: Next.js catch-all admin proxy used request.text() for all body types — corrupts binary multipart; fixed to use request.arrayBuffer() when Content-Type is multipart/form-data
- [Phase 19]: SkillMetadataPanel only renders in card grid view (not table view) — deliberate: table rows are too narrow for metadata display
- [Phase 19]: Pydantic 422 detail is an array of objects, not a string — use-admin-artifacts.ts create() must extract detail[0].msg, not cast detail to string
- [Phase 20]: [20-01]: Non-CONCURRENTLY GIN index — dev DB is small, avoids autocommit isolation complexity
- [Phase 20]: [20-01]: 'simple' tsvector config (not 'english') — required for Vietnamese text support (SKCAT-02)
- [Phase 20]: [20-01]: No tsvector ORM column — GIN functional index managed purely in SQL, invisible to SQLAlchemy
- [Phase 20]: [20-02]: user catalog (GET /api/skills) shows all active skills without ACL join — ACL enforced only at run time per SKCAT-03
- [Phase 20]: [20-02]: browse_skills uses in-memory offset pagination (items[cursor:cursor+limit]) — index in-memory from cached_index; no DB-level OFFSET needed
- [Phase 20]: [20-02]: SkillBrowseItem convenience fields (category, tags, license, author, source_url) extracted from metadata dict — simplifies frontend display
- [Phase 20]: [20-03]: User /skills page uses ArtifactCardGrid read-only (no action props) — locked by CONTEXT.md decision
- [Phase 20]: [20-03]: Admin filter bars use client-side filtering on fetched items — avoids hook modification, acceptable for small admin datasets
- [Phase 20]: [20-04]: usage_count incremented for both procedural and instructional skills — both represent successful user engagement
- [Phase 20]: [20-04]: detail drawer implemented as fixed aside panel — consistent with existing inline dialog pattern, no external Sheet component needed
- [Phase 20]: [20-04]: card onClick opens drawer not confirm dialog — SKCAT-04 requires metadata view before import
- [Phase 20]: [20-05]: Used local _SkillDef alias in _skill_executor_node for usage_count increment — avoids redundant top-level import, fresh get_session() per branch avoids closed-session reuse
- [Phase 20]: [20-06]: disableInternalSort prop bypasses internal sort entirely — column-header sort buttons still work if user clicks them (secondary sort override, acceptable UX)
- [Phase 20]: [20-06]: usageCount: number (required, not optional) — backend always returns this field; nullish coalescing ?? 0 handles any legacy rows
- [Phase 21]: allowed_tools=None or [] is permissive — backwards-compatible with all existing skills that have no allowed_tools declaration
- [Phase 21]: [21-02]: Pre-gate fires before get_tool() call — no DB lookup on denied tool calls (performance + principle of least privilege)
- [Phase 21]: [21-03]: null baseline guard — source_hash=None stores hash without pending_review row, avoids spurious first-run review flood
- [Phase 21]: [21-03]: _check_single_skill uses separate async_session() contexts for read and write — avoids holding sessions across slow HTTP fetches
- [Phase 21]: [21-01]: author_verification removed — always returned 50 (no security value); replaced by dependency_risk and data_flow_risk
- [Phase 21]: [21-01]: undeclared third-party import returns 0 immediately — conservative default for unknown code
- [Phase 21]: [21-04]: SecurityScanner hard veto: dependency_risk==0 with scripts_content forces reject regardless of weighted sum — weighted scoring alone cannot enforce undeclared-import rejection
- [Phase 21]: [21-04]: Frontmatter dependencies: takes priority over scripts/requirements.txt — SKILL.md is the authoritative declaration

### Pending Todos

- [ ] Start WhatsApp Business API verification process (takes 1-4 weeks, needed for future live testing)
- [ ] Add CREDENTIAL_ENCRYPTION_KEY to production .env before OAuth flows (deferred to v1.4)
- [ ] [POST-MVP] HashiCorp Vault for secret management
- [ ] [TECH-DEBT] Fix frontend `pnpm build` failure — SWR hooks in Server Components cause prerender crash on `/settings/integrations` and `/settings/memory` pages. Root cause: `useSWR()` destructuring (`const { data } = useSWR(...)`) runs during static export where SWR context is undefined. Fix: add `"use client"` directive to affected pages, or move SWR calls into client sub-components.
- [ ] [LLM] Switch back to qwen3.5:cloud when weekly Ollama limit resets (currently qwen2.5:7b local)
- [ ] [UI] LLM model and provider configurable in admin console — see .planning/todos/pending/2026-03-08-llm-model-and-provider-configurable-in-admin-console.md — currently using qwen2.5:7b (local) as fallback. Update infra/litellm/config.yaml model entries.
- [ ] [SKILL-PLATFORM] Support GitHub repositories as skill sources in Skill Store — currently only agentskills-index.json protocol supported. Add GitHub adapter: fetch repo file tree, detect skill files (YAML/JSON frontmatter), build index on-the-fly. Allow entering a GitHub repo URL (e.g., github.com/user/repo) in Add Repository dialog alongside agentskills-index.json URLs.
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
| Phase 20 P01 | 526455 | 2 tasks | 2 files |
| Phase 20 P03 | 2m | 2 tasks | 3 files |
| Phase 20 P04 | 162 | 2 tasks | 2 files |
| Phase 20 P05 | 5 | 1 tasks | 1 files |
| Phase 20 P06 | 2m | 2 tasks | 3 files |
| Phase 21 P02 | 2 | 1 tasks | 2 files |
| Phase 21 P03 | 15 | 2 tasks | 5 files |
| Phase 21 P01 | 5 | 1 tasks | 2 files |
| Phase 21 P04 | 8 | 1 tasks | 3 files |

## Session Continuity

Last session: 2026-03-08
Stopped at: Completed 21-04-PLAN.md — SkillImporter dependency/scripts extraction + SecurityScanner hard veto (SKSEC-01). Phase 21 complete (4/4 plans).
Resume file: .planning/phases/21-skill-platform-c-dependency-security-hardening/21-04-SUMMARY.md
