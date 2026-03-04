# Project Research Summary

**Project:** Blitz AgentOS v1.3 — Production Readiness & Skill Platform
**Domain:** Enterprise on-premise agentic operating system (~100 users, Docker Compose)
**Researched:** 2026-03-05 (v1.3 additions layered on v1.0–v1.2 foundation)
**Confidence:** HIGH

---

## Executive Summary

Blitz AgentOS v1.3 is a hardening and platform-maturity release layered on a fully functional v1.2 system. v1.2 shipped dual auth (Keycloak SSO + local bcrypt), 3-gate security (JWT/RBAC/Tool ACL), master agent + sub-agents with 3-tier memory, visual workflow canvas with HITL, multi-channel delivery (Telegram live, WhatsApp/Teams code-complete), admin dashboard with AI wizard, agentskills.io-compliant export, SecurityScanner quarantine, and Grafana/Loki/Alloy observability. v1.3 adds five feature clusters: (A) session and auth hardening via Next.js middleware, (B) navigation redesign and user preferences, (C) embedding sidecar extraction, (D) Keycloak runtime configuration, and (E) skill platform with catalog, discovery, and spec compliance. The core stack is unchanged — no new frameworks are introduced. New dependencies are minimal and well-motivated.

The recommended build sequence is strictly dependency-driven. Auth hardening (Cluster A) ships first because profile, user preferences, and Keycloak admin config all require a reliable, secure session. Navigation (Cluster B) comes second to provide wayfinding to all new pages. Embedding sidecar (Cluster C) is architecturally independent and can run in parallel with Cluster B. Keycloak runtime config (Cluster D) comes after session is proven stable. The skill platform (Cluster E) is additive to v1.2 and comes last. The key constraint is that Next.js must be upgraded to 15.2.3+ before any `middleware.ts` is written — CVE-2025-29927 (CVSS 9.1, middleware bypass) affects all prior versions.

The top four risks for v1.3 are: (1) shipping `middleware.ts` without upgrading Next.js to 15.2.3+ — a known-exploited critical CVE; (2) dual-load of bge-m3 during sidecar migration (model loads in uvicorn, Celery worker, and sidecar simultaneously, consuming ~4GB RAM silently unless extraction is atomic); (3) making Keycloak optional incompletely, breaking config.py startup validation or Celery scheduled workflows for local users; (4) agentskills.io name constraint violations in existing DB skills silently producing non-compliant exports. All four are fully preventable with the mitigations in PITFALLS.md.

---

## Key Findings

### Recommended Stack

The v1.3 stack adds six targeted components to the locked v1.2 foundation. The most architecturally significant is the embedding sidecar: replacing in-process FlagEmbedding (currently loading 1.3+ GB into the uvicorn process with 10–15s cold-start latency) with an `infinity-emb` Docker service accessed via HTTP. This eliminates memory pressure on FastAPI, enables model hot-swap via env var (`INFINITY_MODEL_ID`), and keeps bge-m3 perpetually warm for sub-100ms query-time embedding. The `infinity-emb` CPU image supports bge-m3 natively and runs comfortably at 100-user scale without GPU. For Next.js route protection, `jose` is the only JWT library compatible with Next.js Edge Runtime — `jsonwebtoken` uses Node.js crypto APIs unavailable at the edge.

**New technologies (v1.3 only):**
- `jose` ^5.x (npm): JWT decode/verify in Edge Runtime for `middleware.ts` — only Edge-compatible JWT library; official Next.js recommendation
- `server-only` (npm): Marks session utilities as server-only, prevents token leakage to client bundle; zero-cost guard
- `infinity-emb` 0.0.77 (Docker, CPU image `michaelf34/infinity:latest-cpu`): bge-m3 sidecar with OpenAI-compatible `/v1/embeddings` — replaces FlagEmbedding in-process; model selected via `INFINITY_MODEL_ID` env var
- `shadcn/ui Sidebar` (shadcn CLI, `collapsible="icon"` variant): Navigation rail — already in project design system via Tailwind/Radix; no new npm dependency
- `skills-ref` 0.1.1 (PyPI, dev-only): CLI validator for agentskills.io spec compliance (`agentskills validate`) — CI use only, not in production backend
- Native PostgreSQL tsvector with GIN index: Skill catalog full-text search — no new library; uses existing SQLAlchemy `func.to_tsvector()` and raw Alembic SQL migration

**Unchanged (locked v1.2):** LangGraph 1.0.9, CopilotKit 1.51.x, Next.js 15.5+, FastAPI 0.115.x, SQLAlchemy 2.0, Keycloak 26.5.x, PostgreSQL 16 + pgvector 0.8.x, LiteLLM Proxy 1.81.x, Celery 5.6.x, Redis 7.x, structlog 25.5.x, MCP SDK 1.26.x.

**Critical version constraint:** Next.js must be confirmed at 15.2.3+ before any `middleware.ts` is written. CVE-2025-29927 (CVSS 9.1) allows complete middleware bypass via `x-middleware-subrequest` header in earlier versions.

### Expected Features

**Must have (required for v1.3 to ship):**
- Next.js `middleware.ts` route protection + HttpOnly session cookie — all `/chat`, `/admin`, `/canvas`, `/profile` routes gated; currently every page does its own auth check ad-hoc
- Session silent refresh (`/api/auth/refresh`) + logout endpoint + UI button — enterprise users expect full-day sessions; logout is a security baseline requirement
- Navigation rail (shadcn/ui Sidebar, icon-only, 4 destinations: Chat/Canvas/Admin/Profile) — without it, the multi-page app has no coherent wayfinding
- Profile page (`/profile`) with name, email, role, logout button, credential management link
- User preferences (thinking mode + response style) — DB table, API endpoints, UI in profile; injected into system prompt via PromptLoader
- Embedding sidecar hot-model at `http://embedding:8003` — memory search is on the hot path for every agent invocation; current in-process embedding adds cold-start latency and consumes 1.3GB RAM in uvicorn
- Keycloak-optional boot — local-auth users must not be blocked when Keycloak is unavailable; Keycloak cannot be a hard boot dependency
- Agent Skills SKILL.md spec compliance with `skills-ref validate` in CI — exported skills must pass spec validation for ecosystem interoperability
- Skill catalog UI at `/admin/skills/catalog` — skills exist in DB but are not browsable
- Skill discovery from external registries — browse and one-click import from configured registry URLs
- Skill dependency hardening — SecurityScanner blocks undeclared subprocess/socket usage in skill scripts

**Should have (P2 — after core P1 is stable):**
- Keycloak admin UI runtime config (URL/realm/client/CA cert stored in `platform_config` table, encrypted; test-connection button; no restart required)
- `allowed-tools` enforcement at Gate 3 — intersect skill's declared tools with user ACL; first platform to enforce this experimental agentskills.io spec field
- Performance instrumentation (7 critical paths: memory search, tool execution, LLM call, canvas compile, MCP call, channel delivery, workflow run) + Grafana panels for p50/p95
- Internal "Promoted Skills" curation in skill catalog (admin badge)

**Defer (v1.4+):**
- Auto-publish skills to agentskills.io public registry — violates on-premise data requirement; admin-controlled export is the correct approach
- Skill ratings/reviews — statistically meaningless at 100 users; usage count is sufficient
- Multi-model embedding — bge-m3 handles Vietnamese + English natively; multiple models would break `vector(1024)` constraint
- Real-time skill install push notifications — operational noise for a curated internal catalog
- Celery periodic registry auto-sync — manual sync is sufficient for v1.3

### Architecture Approach

v1.3 makes no changes to the established five-layer architecture. The new components slot into existing layers without restructuring anything. The most significant structural change is the `app/(protected)/` Next.js route group — moving all authenticated pages under this group allows the navigation rail to apply only to authenticated routes without wrapping `/login` or API routes. The embedding sidecar adds a new Layer 5 infrastructure service and shifts the Layer 4b memory subsystem from in-process FlagEmbedding to HTTP calls. Keycloak runtime config shifts a static env-var-based config value into a DB-backed runtime record loaded by the security layer. All other changes are additive.

**Components and v1.3 changes:**
1. `middleware.ts` (new): Optimistic cookie check at Edge Runtime; redirects unauthenticated users; `jose` for JWT verify; CVE-patched Next.js 15.2.3+ required
2. `app/(protected)/layout.tsx` (new): Route group layout containing nav rail; root `app/layout.tsx` stays minimal (only providers that must wrap everything)
3. `embedding/` Docker service (new): `infinity-emb` serving bge-m3 at `http://embedding:8003`; backend `memory/embeddings.py` calls sidecar first, Celery fallback if unreachable
4. `platform_config` DB table (new migration 020): Stores Keycloak connection config (URL, realm, client ID, client secret, CA cert) encrypted; loaded by `security/jwt.py` at runtime
5. `/admin/skills/catalog` (new route): PostgreSQL tsvector FTS with `'simple'` dictionary (handles Vietnamese); GIN index via raw Alembic `op.execute()` (not autogenerate)
6. `normalize_skill_name()` + `skills-ref validate` in CI: Enforces agentskills.io name constraints at creation time; validates exported ZIP structure

### Critical Pitfalls

Research identified 15 pitfalls across the v1.0–v1.3 combined research. The highest-priority for v1.3:

1. **CVE-2025-29927 — middleware auth bypass (CRITICAL)** — Adding `middleware.ts` to a Next.js version < 15.2.3 ships a known-exploited CVSS 9.1 vulnerability. Attackers skip auth entirely by sending `x-middleware-subrequest: middleware` header. Prevention: confirm Next.js version, upgrade to 15.2.3+ before writing any middleware; strip the header at reverse proxy; treat middleware as UX convenience only — backend 3-gate security is the real enforcement.

2. **Middleware infinite redirect loop** — Redirect logic written as "where should this user go?" fires on every request including the destination, causing `ERR_TOO_MANY_REDIRECTS`. Prevention: authenticated users always get `NextResponse.next()`; matcher must explicitly exclude `/login`, `/_next`, `/api`; remove per-page auth redirect logic from existing pages after middleware is added.

3. **Embedding sidecar dual-load** — Adding the sidecar without atomically removing in-process FlagEmbedding loads bge-m3 in three processes simultaneously (~4GB RAM, invisible without memory profiling). Prevention: sidecar addition and `BGE_M3Provider` import removal must be in one commit; add a test asserting `BGE_M3Provider` is not imported from `backend/agents/`; `depends_on: condition: service_healthy` in docker-compose.

4. **Keycloak optional boot — partial fix breaks startup** — `config.py` declares `keycloak_url: str` as required; Celery workflow execution calls Keycloak Admin API for local users (returns 404). Prevention: change to `keycloak_url: str = ""` with pydantic-settings v2 conditional `@field_validator`; add `if not settings.keycloak_enabled:` guards to all Keycloak service calls; fix workflow execution path to use `owner_roles_json` snapshot for local users.

5. **PostgreSQL tsvector language mismatch disables GIN index** — Index created with `to_tsvector('english', ...)` but query uses `to_tsvector(...)` (implicit language) causes silent sequential scan; `'english'` also fails to stem Vietnamese content. Prevention: always use `'simple'` explicitly in both GIN index definition AND query; verify with `EXPLAIN ANALYZE` before shipping — must show "Bitmap Index Scan", not "Seq Scan".

6. **agentskills.io name constraints fail silently on existing skills** — Existing DB skills with names like `"Email Fetch v2"` (spaces, uppercase) produce non-compliant exports. Prevention: add `normalize_skill_name()` slugifier; validate at skill creation time in wizard, not only at export; run `skills-ref validate` in CI on exported ZIPs.

---

## Implications for Roadmap

Based on the dependency graph in FEATURES.md and the existing phase ordering from ARCHITECTURE.md, v1.3 decomposes into 5 phases:

### Phase 1: Session & Auth Hardening

**Rationale:** FEATURES.md explicitly states "Cluster A is prerequisite for everything else in v1.3." Every v1.3 feature — profile page, user preferences, Keycloak config, skill catalog admin access — requires a reliable, secure session. Writing `middleware.ts` on an unpatched Next.js ships CVE-2025-29927. Auth must be correct before building features on top of it.

**Delivers:** Next.js upgraded to 15.2.3+; `middleware.ts` with `jose` for Edge Runtime JWT verify; HttpOnly + Secure + SameSite=Lax session cookie; silent refresh via `/api/auth/refresh`; `POST /api/auth/logout` clears all cookies; Keycloak-optional boot (local users can log in when Keycloak is unavailable); Keycloak status shown in admin Health panel.

**Addresses features:** Cluster A (session & auth hardening) entirely; Keycloak-optional boot prerequisite (part of Cluster D).

**Avoids pitfalls:** CVE-2025-29927 (Pitfall 9 — Next.js upgrade before any middleware is written); infinite redirect loop (Pitfall 8 — authenticated users always NextResponse.next()); Keycloak partial-optional fix (Pitfall 10 — `config.py` validation and Celery workflow path for local users fixed here).

**Research flag:** Standard patterns — Next.js 15.2.3+ auth with `jose` is the official recommended pattern; CVE details are fully documented. Skip `/gsd:research-phase`. Validate Next.js version and `jose` Edge Runtime behavior during plan writing.

---

### Phase 2: Navigation & User Experience

**Rationale:** Navigation rail connects the new pages being built in Phases 3–5. Profile page hosts user preferences. Both require stable auth from Phase 1. Navigation restructure (`app/(protected)/`) must precede adding pages under the protected layout.

**Delivers:** `app/(protected)/layout.tsx` route group containing navigation rail; shadcn/ui Sidebar with `collapsible="icon"` variant (Chat/Canvas/Admin/Profile icons); Profile page (`/profile`) with user info, role from JWT claims, logout button; `user_preferences` table (migration 021); API endpoints for preferences; thinking mode + response style UI in profile page; preferences injected into system prompt via PromptLoader.

**Addresses features:** Cluster B (navigation rail, profile page, user preferences) entirely.

**Avoids pitfalls:** Root layout wrapping login and API routes (Pitfall 14 — `app/(protected)/` route group is the correct containment; `app/layout.tsx` stays minimal); A2UI cards and channel message formatters must be audited for hardcoded route strings before restructure.

**Research flag:** Standard patterns — shadcn/ui Sidebar `collapsible="icon"` and Next.js route groups are well-documented official patterns. Skip `/gsd:research-phase`.

---

### Phase 3: Performance & Embedding Sidecar

**Rationale:** Embedding sidecar is architecturally independent — no dependency on navigation or preferences. Can run in parallel with Phase 2 if capacity allows. Memory search is on the hot path for every agent invocation; current in-process embedding adds 10–15s cold-start latency and 1.3GB RAM pressure to uvicorn. Performance instrumentation (7 critical paths) is low-cost and ships in this phase to baseline current performance before any optimization.

**Delivers:** `infinity-emb` Docker sidecar (`michaelf34/infinity:latest-cpu`) at port 8003 with `INFINITY_MODEL_ID=BAAI/bge-m3`; `embedding_cache` Docker volume for model weight persistence; backend `memory/embeddings.py` refactored to call sidecar via `httpx` with Celery fallback; in-process `BGE_M3Provider` removed from `agents/` and `memory/`; `duration_ms` structlog fields on all 7 critical paths; Grafana panels for p50/p95 per operation.

**Addresses features:** Cluster C (embedding sidecar, performance instrumentation) entirely.

**Avoids pitfalls:** Dual-load of bge-m3 (Pitfall 11 — sidecar add + FlagEmbedding removal is one atomic commit; add test asserting no `BGE_M3Provider` import from `agents/`); `transformers<5.0` pin maintained in sidecar image; `depends_on: condition: service_healthy` ensures backend waits for sidecar warm model.

**Research flag:** Needs targeted research during planning — specifically `infinity-emb` Docker image startup configuration (model pre-download path, health endpoint format, startup time on cold model cache). The pattern is established but `michaelf34/infinity:latest-cpu` image-specific details should be validated against the live image before writing the plan.

---

### Phase 4: Keycloak Runtime Configuration

**Rationale:** Keycloak runtime config is built on the admin dashboard (v1.2) and must follow Phase 1's Keycloak-optional boot fix (the admin UI config stores Keycloak connection settings in DB — this is only coherent if the optional boot is working first). Must come after Phase 1 is confirmed stable to avoid auth regressions. Completes the Cluster D work started in Phase 1.

**Delivers:** `platform_config` DB table (migration 022) with encrypted sensitive fields (client secret, CA cert); admin UI form for Keycloak URL/realm/client ID/client secret/CA cert path; `POST /api/admin/keycloak/test-connection` (attempts JWKS fetch, returns `{reachable: bool, error?: string}`); backend reloads JWKS from `platform_config` on save without restart; existing `.env` values remain as fallback defaults.

**Addresses features:** Cluster D (Keycloak admin UI runtime config, Keycloak-optional boot completion) entirely.

**Avoids pitfalls:** Keycloak JWKS key rotation (Integration Gotchas — JWKS cache with 5–10 minute TTL, fetch-fresh fallback on validation failure); Keycloak partial-optional fix completeness verification (Pitfall 10 — `KEYCLOAK_ENABLED=false` CI test with `KEYCLOAK_URL` unset asserts HTTP 200 on `/health`).

**Research flag:** Needs targeted research during planning — pydantic-settings v2 `@field_validator` pattern for conditional required fields; Keycloak Admin REST API endpoint for connection testing (JWKS endpoint reachability vs. full admin credential validation). MEDIUM confidence on implementation specifics; confirm before writing plan.

---

### Phase 5: Skill Platform

**Rationale:** The skill platform (catalog, discovery, compliance, dependency hardening) layers additively on v1.2 skill import/export with no risk to existing functionality. Comes after navigation (Phase 2) because the catalog is in the admin desk, and after auth (Phase 1) because skill management is admin-gated. `allowed-tools` enforcement depends on spec compliance being verified first.

**Delivers:** `normalize_skill_name()` slugifier + validation at wizard creation time; agentskills.io SKILL.md spec-compliant name/description/directory structure; `skills-ref validate` in CI for exported ZIPs; tsvector FTS GIN index (`'simple'` language, raw SQL migration) on `skills` table; `/admin/skills/catalog` with search/filter (category, status, author)/sort UI and skill detail view; external registry browse panel (paginated index from configured registry URLs, one-click import into existing SecurityScanner flow); skill dependency hardening (scanner blocks undeclared subprocess/socket/OS calls in `scripts/` directory); `allowed-tools` enforcement at Gate 3 (intersect skill declared tools with user ACL, log denials); internal "Promoted Skills" admin curation badge.

**Addresses features:** Cluster E (skill platform) entirely.

**Avoids pitfalls:** agentskills.io name constraints (Pitfall 15 — normalize at creation, not export; CI validates); tsvector language mismatch (Pitfall 12 — `'simple'` config in both index and query; `EXPLAIN ANALYZE` verification before ship); LangGraph HITL checkpoint topology (Pitfall 13 — drain `status='pending_hitl'` workflow runs before any graph changes related to skill execution nodes).

**Research flag:** Needs targeted research during planning — external registry index format (how agentskills.io and GitHub-based registries structure their discoverable skill indexes; no formal protocol documented beyond the SKILL.md spec itself). HIGH confidence on the SKILL.md spec (official source); MEDIUM confidence on registry discovery protocols.

---

### Phase Ordering Rationale

- **Auth first:** Session hardening is the explicit prerequisite for all other v1.3 clusters per the FEATURES.md dependency graph. Shipping new features before auth is secure creates unprotected pages and an insecure foundation.
- **Navigation second:** All new pages (profile, skill catalog, Keycloak config) are added to the admin desk or protected area. The route group restructure must precede adding pages under it.
- **Sidecar independent:** No other phase depends on the embedding sidecar. Can run parallel to Phase 2 if developer capacity allows. Placed as Phase 3 to ensure auth foundation is proven before adding a new service dependency.
- **Keycloak config after proven auth:** Admin UI for OIDC configuration touches the auth critical path. Building it before session hardening is verified risks an auth regression in a high-value admin feature.
- **Skill platform last:** Fully additive to v1.2. All security gates (auth, RBAC, Tool ACL, SecurityScanner) must be stable before adding skill execution paths through them. `allowed-tools` enforcement requires spec compliance to be verified first.

### Research Flags

**Phases needing targeted research during planning:**
- **Phase 3 (Embedding Sidecar):** `infinity-emb` Docker image startup behavior — model pre-download path, health endpoint format, cold-start time on first run. The sidecar pattern is established but image-specific details need live validation.
- **Phase 4 (Keycloak Runtime Config):** pydantic-settings v2 conditional validator pattern; Keycloak Admin REST API endpoint for OIDC connection verification. MEDIUM confidence on these specifics.
- **Phase 5 (Skill Platform):** External registry discovery index format and protocol — agentskills.io registry API vs. self-hosted index format. Need to decide the format before building the browse panel.

**Phases with standard, well-documented patterns (skip research-phase):**
- **Phase 1 (Session & Auth Hardening):** Next.js 15.2.3+ auth with `jose` + HttpOnly cookies is the official recommended pattern; CVE details are fully documented.
- **Phase 2 (Navigation & UX):** shadcn/ui Sidebar `collapsible="icon"` variant and `app/(protected)/` route groups are official Next.js App Router patterns.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack (v1.3 additions) | HIGH | `jose`, `infinity-emb`, `skills-ref`, shadcn/ui Sidebar all verified from official/PyPI sources. CVE-2025-29927 confirmed from Vercel postmortem. `transformers<5.0` pin must propagate to sidecar image. |
| Features | HIGH | Auth cluster from official Next.js docs (HIGH). agentskills.io spec from official source (HIGH). Embedding sidecar pattern from open-source reference (MEDIUM). Navigation rail from established HCI pattern (MEDIUM). Overall HIGH for the auth-critical features that matter most. |
| Architecture | HIGH | Five-layer architecture is the confirmed existing design. v1.3 changes are additive and architecturally conservative. Route group and sidecar integration are official patterns. `app/(protected)/` restructure is the most structural change; risk is low. |
| Pitfalls | HIGH | 15 pitfalls identified across v1.0–v1.3. Critical ones (CVE, dual-load, tsvector index mismatch, Keycloak partial-optional) are code-verified or documented in official sources. Phase assignments and prevention patterns are concrete. |

**Overall confidence:** HIGH

### Gaps to Address

- **`infinity-emb` Docker image startup behavior:** Model pre-download path, cold start timing, and health endpoint format should be validated against the live `michaelf34/infinity:latest-cpu` image during Phase 3 plan writing. STACK.md notes ~30s cold start on first run when model cache is empty.

- **Keycloak Admin REST API for connection testing:** The `POST /api/admin/keycloak/test-connection` feature may require calling the Keycloak JWKS endpoint with new config credentials. The exact API endpoint and auth pattern for this use case should be confirmed during Phase 4 planning. MEDIUM confidence on specifics.

- **External registry discovery protocol:** FEATURES.md specifies admin-configured registry URLs but the index format for self-hosted registries is not formally specified by agentskills.io. A decision needs to be made during Phase 5 planning — likely a simple JSON array at `/index.json` per registry URL. Evaluate what format the agentskills.io public registry uses if it exposes one.

- **`skills-ref` alpha status in CI:** `skills-ref` 0.1.1 is Alpha quality (STACK.md notes this explicitly). Evaluate its false-positive rate and spec version drift risk before committing it to CI. The fallback is a custom validator built from the official SKILL.md spec YAML schema.

- **`operator_roles_json` snapshot for Keycloak-optional scheduled workflows:** PITFALLS.md (Pitfall 10) notes that Celery workflow execution calls Keycloak Admin API for local users. The fix — using `owner_roles_json` snapshot directly for local users — must be tested with a CI scenario of `KEYCLOAK_ENABLED=false` plus a running scheduled workflow owned by a local user.

---

## Sources

### Primary (HIGH confidence)

- agentskills.io/specification (official spec, fetched directly 2026-03-05) — SKILL.md format, name/description constraints, `allowed-tools` field, directory structure
- agentskills.io/integrate-skills (official) — Integration pattern for agent platforms, progressive disclosure model
- nextjs.org/docs/app/guides/authentication (official Next.js auth guide) — `middleware.ts`, DAL pattern, HttpOnly cookie, `jose` recommendation
- nextjs.org/blog/cve-2025-29927 (Vercel postmortem) — CVE-2025-29927 details, 15.2.3+ requirement, defense-in-depth guidance
- pypi.org/project/infinity-emb/ (v0.0.77, PyPI) — bge-m3 sidecar, Docker image variants, model support
- npmjs.com/package/jose — Edge Runtime JWT library, Web Crypto API compatibility
- keycloak.org/server/all-config (official) — Build vs runtime config distinction
- keycloak.org/docs-api/latest/rest-api (official) — Realm/client/IDP management endpoints
- ui.shadcn.com/docs/components/radix/sidebar — Sidebar component, `collapsible="icon"` variant, SidebarProvider
- postgresql.org/docs/current/datatype-textsearch.html (official) — tsvector, GIN index, language configuration
- sqlalchemy/alembic issue #1390 (GitHub) — Alembic GIN expression index autogenerate false positives

### Secondary (MEDIUM confidence)

- github.com/puppetm4st3r/baai_m3_simple_server — Reference implementation for bge-m3 FastAPI sidecar (asyncio batching, RequestProcessor pattern)
- workos.com/blog/nextjs-app-router-authentication-guide-2026 — Next.js App Router auth patterns, middleware + DAL details
- github.com/michaelfeil/infinity — `infinity-emb` Docker deployment pattern, bge-m3 support confirmation
- arxiv.org/html/2603.02176 — Agent Skills ecosystem scale data, power-law distribution in skill discovery
- pypi.org/project/skills-ref/ (0.1.1, Jan 2026) — CLI commands, alpha status disclosure
- keycloak.org/docs-api and forum — Keycloak OIDC client config via Admin REST API

### Tertiary (LOW confidence)

- groovyweb.co/blog/ui-ux-design-trends-ai-apps-2026 — Navigation rail context for AI apps (marketing content, directionally useful)
- smartscope.blog/skillsmp-marketplace-guide — Catalog UX patterns and discovery scale (extrapolated to enterprise use case)

---
*Research completed: 2026-03-05*
*Ready for roadmap: yes*
