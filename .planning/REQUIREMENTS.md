# v1.3 Requirements — Production Readiness & Skill Platform

**Milestone:** v1.3
**Created:** 2026-03-05
**Design:** `docs/plans/2026-03-05-v1.3-production-readiness-design.md`
**Research:** `.planning/research/SUMMARY.md`

---

## Session & Auth Hardening

- [x] **AUTH-01**: Protected routes (`/chat`, `/admin`, `/canvas`, `/profile`, `/workflows`, `/skills`, `/settings`) redirect unauthenticated users to `/login` via Next.js `middleware.ts` using `jose` for Edge Runtime JWT verification
- [x] **AUTH-02**: Next.js upgraded to ≥15.2.3 before any `middleware.ts` is written (CVE-2025-29927 mitigation — CVSS 9.1 middleware bypass)
- [x] **AUTH-03**: Session cookie set with `HttpOnly`, `Secure` (production), `SameSite=Lax` — JWT never stored in localStorage
- [x] **AUTH-04**: Session silent refresh via `/api/auth/refresh` renews access token when it has <5 min remaining, using HttpOnly refresh token cookie (7d TTL)
- [x] **AUTH-05**: User can log out via `POST /api/auth/logout` which clears all auth cookies; Keycloak path also calls Keycloak logout endpoint
- [x] **AUTH-06**: Client-side `SessionProvider` wrapper detects `session.error` (`SessionExpired`, `RefreshAccessTokenError`) and auto-redirects to `/login`
- [x] **AUTH-07**: Chat page server component validates access token with backend on each load — if 401, triggers signOut + redirect

## Navigation & User Experience

- [x] **NAV-01**: Vertical navigation rail (56px) with icon items (Chat, Workflows, Skills, Settings, Admin, Profile) is visible on all authenticated pages
- [x] **NAV-02**: Admin nav item is visible only to users with `admin`, `developer`, or `it-admin` roles
- [x] **NAV-03**: Active nav item is visually highlighted; clicking avatar opens dropdown with Profile and Sign Out
- [x] **NAV-04**: Authenticated pages use `app/(authenticated)/layout.tsx` route group — `/login` and API routes are excluded from nav rail
- [x] **NAV-05**: User can view their profile at `/profile` showing name, email, auth provider badge (SSO/Local), roles, current session expiry, and logout button
- [x] **NAV-06**: Local users can change their password from the profile page
- [x] **NAV-07**: User can set LLM thinking mode preference (on/off) from profile page, persisted in `user_preferences` table (JSONB)
- [x] **NAV-08**: User can set response style preference (concise/detailed/conversational) from profile page, persisted in `user_preferences` table
- [x] **NAV-09**: User preferences are injected into agent system prompt via PromptLoader on each invocation
- [x] **NAV-10**: Backend exposes `GET /api/users/me/preferences` and `PUT /api/users/me/preferences` endpoints with JWT-based user identification

## Performance & Embedding Sidecar

- [x] **PERF-01**: Embedding sidecar service (`infinity-emb` or equivalent) runs as a Docker Compose service, loads embedding model at startup, and exposes `POST /embed` and `POST /embed/batch` HTTP endpoints
- [x] **PERF-02**: Embedding model is configurable via `EMBEDDING_MODEL` env var (default: `BAAI/bge-m3`); sidecar health endpoint reports model name, dimension, and status
- [x] **PERF-03**: Backend `memory/embeddings.py` calls sidecar HTTP first; falls back to Celery path if sidecar is unreachable
- [x] **PERF-04**: In-process FlagEmbedding (`BGE_M3Provider`) is removed from backend — no dual-load of bge-m3 in uvicorn and sidecar simultaneously
- [x] **PERF-05**: Admin can trigger memory reindex via `POST /api/admin/memory/reindex` with `confirm=true` — deletes all vectors and re-embeds from source text (with warning about data loss)
- [x] **PERF-06**: Backend validates sidecar model dimension matches pgvector column dimension on startup — blocks embedding operations with clear error on mismatch
- [x] **PERF-07**: `duration_ms` is logged via structlog for 7 critical paths: memory search, tool execution, LLM call, canvas compile, MCP call, channel delivery, workflow run
- [x] **PERF-08**: Single DB session per request via contextvar replaces 6-9 separate session opens
- [x] **PERF-09**: Tool ACL query results cached with 60s TTL per user
- [x] **PERF-10**: Episode threshold check cached with 60s TTL
- [x] **PERF-11**: User instructions cached per-user with LRU and 60s TTL
- [x] **PERF-12**: JWKS refresh uses `asyncio.Lock` to prevent thundering herd on concurrent requests
- [x] **PERF-13**: `useSkills()` hook hoisted above CopilotKit key boundary to prevent re-mount on every agent response

## Identity Configuration (Keycloak Runtime)

- [x] **IDCFG-01**: Backend boots with local auth only when no Keycloak config exists — Keycloak is not a required boot dependency
- [x] **IDCFG-02**: Health endpoint reports auth mode: `{"auth": "local-only"}` or `{"auth": "local+keycloak"}`
- [x] **IDCFG-03**: Login page conditionally renders "Sign in with SSO" button based on `GET /api/auth/config` response
- [x] **IDCFG-04**: Admin can configure Keycloak connection (Issuer URL, Client ID, Client Secret, Realm, CA cert path) via admin UI Identity tab
- [x] **IDCFG-05**: Admin can test Keycloak connection before saving — `POST /api/admin/keycloak/test-connection` validates JWKS endpoint reachability
- [x] **IDCFG-06**: Keycloak config stored in `platform_config` DB table with sensitive fields encrypted; backend reloads JWKS on save without restart
- [x] **IDCFG-07**: Config resolution: DB `platform_config` (priority) → env vars (fallback) → not configured (local-only mode)
- [x] **IDCFG-08**: Admin can disable SSO via "Disable SSO" button with confirmation — reverts to local-only auth

## Skill Platform — Standards Compliance

- [ ] **SKSTD-01**: Skill names validated at creation time: max 64 chars, lowercase alphanumeric + hyphens, no consecutive hyphens, matches directory name (agentskills.io spec)
- [ ] **SKSTD-02**: `skill_definitions` table extended with columns: `license`, `compatibility`, `metadata_json`, `allowed_tools`, `source_url`, `source_hash`, `tags`, `category`
- [ ] **SKSTD-03**: SKILL.md importer parses all standard frontmatter fields (name, description, license, compatibility, metadata, allowed-tools)
- [ ] **SKSTD-04**: Skill exporter produces agentskills.io-compliant ZIP with SKILL.md + MANIFEST.json + assets directory
- [ ] **SKSTD-05**: ZIP bundle import extracts SKILL.md + MANIFEST.json + assets, validates structure before processing

## Skill Platform — Discovery & Catalog

- [x] **SKCAT-01**: Skill catalog at `/admin/skills/catalog` (or `/skills`) with search (name/description via PostgreSQL tsvector FTS), filter (category, status, author), sort (date, usage), and skill detail view
- [x] **SKCAT-02**: PostgreSQL tsvector uses `'simple'` language config (not `'english'`) for Vietnamese support; GIN index created via raw SQL Alembic migration
- [ ] **SKCAT-03**: Tool catalog backend provides search/filter by handler_type, status, and name
- [ ] **SKCAT-04**: Admin can browse external skill registries from configured registry URLs with paginated index
- [ ] **SKCAT-05**: One-click import from external registry triggers existing SecurityScanner + quarantine flow

## Skill Platform — Dependency & Security Hardening

- [ ] **SKSEC-01**: Skills with `scripts/` directory must declare dependencies explicitly; SecurityScanner blocks undeclared subprocess/socket/os.system usage
- [ ] **SKSEC-02**: `allowed-tools` enforcement: SkillExecutor restricts tool calls to intersection of skill's declared `allowed-tools` and user's ACL; denied calls logged to audit
- [ ] **SKSEC-03**: Update checker (Celery periodic task) re-fetches `source_url`, compares hash, creates `pending_review` version if changed
- [ ] **SKSEC-04**: SecurityScanner enhanced with dependency risk factor (20%) and data flow analysis factor (replaces author verification 10%)

## Skill Platform — Sharing & Marketplace

- [ ] **SKMKT-01**: Admin can mark skills as "Promoted" in catalog — promoted skills appear in a curated section visible to all users
- [ ] **SKMKT-02**: Users can export skills as agentskills.io-compliant ZIP download from catalog UI
- [ ] **SKMKT-03**: Skill sharing between users via existing `artifact_permissions` system

## Skill Platform — Enhanced Builder

- [ ] **SKBLD-01**: Builder generates complete `procedure_json` with steps, tool references, conditions, and prompt templates for procedural skills
- [ ] **SKBLD-02**: Builder generates `instruction_markdown` for instructional skills with proper Agent Skills format
- [ ] **SKBLD-03**: For tools: builder generates handler code scaffolding (Python function stub with Pydantic I/O models)
- [ ] **SKBLD-04**: Builder searches cached external repo indexes for similar skills and shows top 3-5 relevant examples as reference
- [ ] **SKBLD-05**: "Fork" capability: user selects an existing external skill as starting point; builder pre-populates and adapts
- [ ] **SKBLD-06**: Every artifact (built or imported) goes through SecurityScanner before activation — `security_review` node added to builder LangGraph
- [ ] **SKBLD-07**: SecurityReportCard A2UI component shows trust score, factor breakdown, tool permissions, injection warnings, and recommendation
- [ ] **SKBLD-08**: For `review` or `reject` recommendations, admin must explicitly approve before skill is activated

---

## Future Requirements (Deferred to v1.4+)

- Real OAuth email/calendar integration (replace mock sub-agents with live Google/Microsoft OAuth)
- WhatsApp Business live end-to-end (pending Meta Business API verification)
- MS Teams live end-to-end (pending Azure Bot Service registration)
- Skill composition (one skill calling another, max depth 3)
- Skill analytics (execution count, success rate, popular skills dashboard)
- Skill versioning UI (version history, diff view, rollback)
- External marketplace connector (skills.sh, skillsmp.com)
- Auto-publish skills to agentskills.io public registry
- Celery periodic registry auto-sync
- Multi-model embedding (bge-m3 handles multilingual natively)
- Real-time skill install push notifications
- Skill ratings and reviews (star system)
- HashiCorp Vault for secret management

## Out of Scope

| Feature | Reason |
|---------|--------|
| Auto-publish to agentskills.io | Violates on-premise data requirement; admin-controlled export sufficient |
| JWT in localStorage | CLAUDE.md mandates HttpOnly cookie; CopilotKit proxy injects JWT server-side |
| Remove local auth (Keycloak-only) | Local auth is emergency fallback for Keycloak outages |
| Skill ratings/reviews | Statistically meaningless at 100 users; usage count sufficient |
| Multi-model embedding per-user | bge-m3 is multilingual; multiple models break `vector(1024)` constraint |
| Kubernetes deployment | Docker Compose for MVP; K8s is post-MVP |
| Real-time skill install notifications | Operational noise for curated internal catalog |

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| AUTH-01 | Phase 15 | Complete |
| AUTH-02 | Phase 15 | Complete |
| AUTH-03 | Phase 15 | Complete |
| AUTH-04 | Phase 15 | Complete |
| AUTH-05 | Phase 15 | Complete |
| AUTH-06 | Phase 15 | Complete |
| AUTH-07 | Phase 15 | Complete |
| NAV-01 | Phase 16 | Complete |
| NAV-02 | Phase 16 | Complete |
| NAV-03 | Phase 16 | Complete |
| NAV-04 | Phase 16 | Complete |
| NAV-05 | Phase 16 | Complete |
| NAV-06 | Phase 16 | Complete |
| NAV-07 | Phase 16 | Complete |
| NAV-08 | Phase 16 | Complete |
| NAV-09 | Phase 16 | Complete |
| NAV-10 | Phase 16 | Complete |
| PERF-01 | Phase 17 | Complete |
| PERF-02 | Phase 17 | Complete |
| PERF-03 | Phase 17 | Complete |
| PERF-04 | Phase 17 | Complete |
| PERF-05 | Phase 17 | Complete |
| PERF-06 | Phase 17 | Complete |
| PERF-07 | Phase 17 | Complete |
| PERF-08 | Phase 17 | Complete |
| PERF-09 | Phase 17 | Complete |
| PERF-10 | Phase 17 | Complete |
| PERF-11 | Phase 17 | Complete |
| PERF-12 | Phase 17 | Complete |
| PERF-13 | Phase 17 | Complete |
| IDCFG-01 | Phase 18 | Complete |
| IDCFG-02 | Phase 18 | Complete |
| IDCFG-03 | Phase 18 | Complete |
| IDCFG-04 | Phase 18 | Complete |
| IDCFG-05 | Phase 18 | Complete |
| IDCFG-06 | Phase 18 | Complete |
| IDCFG-07 | Phase 18 | Complete |
| IDCFG-08 | Phase 18 | Complete |
| SKSTD-01 | Phase 19 | pending |
| SKSTD-02 | Phase 19 | pending |
| SKSTD-03 | Phase 19 | pending |
| SKSTD-04 | Phase 19 | pending |
| SKSTD-05 | Phase 19 | pending |
| SKCAT-01 | Phase 20 | Complete |
| SKCAT-02 | Phase 20 | Complete |
| SKCAT-03 | Phase 20 | pending |
| SKCAT-04 | Phase 20 | pending |
| SKCAT-05 | Phase 20 | pending |
| SKSEC-01 | Phase 21 | pending |
| SKSEC-02 | Phase 21 | pending |
| SKSEC-03 | Phase 21 | pending |
| SKSEC-04 | Phase 21 | pending |
| SKMKT-01 | Phase 22 | pending |
| SKMKT-02 | Phase 22 | pending |
| SKMKT-03 | Phase 22 | pending |
| SKBLD-01 | Phase 23 | pending |
| SKBLD-02 | Phase 23 | pending |
| SKBLD-03 | Phase 23 | pending |
| SKBLD-04 | Phase 23 | pending |
| SKBLD-05 | Phase 23 | pending |
| SKBLD-06 | Phase 23 | pending |
| SKBLD-07 | Phase 23 | pending |
| SKBLD-08 | Phase 23 | pending |

---
*Generated: 2026-03-05 from approved v1.3 design and research*
*Traceability updated: 2026-03-05 by roadmapper — 53/53 requirements mapped to phases*
