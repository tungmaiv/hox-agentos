# Roadmap: Blitz AgentOS

## Milestones

- ✅ **v1.0 MVP** — Phases 1–3.1 (shipped 2026-02-26)
- ✅ **v1.1 Enterprise Platform** — Phases 4–10 (shipped 2026-03-02)
- ✅ **v1.2 Developer Experience** — Phases 11–14 (shipped 2026-03-04)
- [ ] **v1.3 Production Readiness & Skill Platform** — Phases 15–23 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–3.1) — SHIPPED 2026-02-26</summary>

- [x] **Phase 1: Identity and Infrastructure Skeleton** — 4/4 plans (completed 2026-02-24)
- [x] **Phase 2: Agent Core and Conversational Chat** — 5/5 plans (completed 2026-02-25)
- [x] **Phase 2.1: Tech Debt Cleanup** (INSERTED) — 1/1 plan (completed 2026-02-26)
- [x] **Phase 3: Sub-Agents, Memory, and Integrations** — 6/6 plans (completed 2026-02-26)
- [x] **Phase 3.1: Memory Read Path & MCP Hot-Registration** (INSERTED) — 1/1 plan (completed 2026-02-26)

Full phase details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 Enterprise Platform (Phases 4–10) — SHIPPED 2026-03-02</summary>

- [x] **Phase 4: Canvas and Workflows** — 5/5 plans (completed 2026-02-27)
- [x] **Phase 4.1: Phase 4 Polish** (INSERTED) — 1/1 plan (completed 2026-02-27)
- [x] **Phase 5: Scheduler and Channels** — 6/6 plans (completed 2026-02-28)
- [x] **Phase 5.1: Workflow Execution Wiring** (INSERTED) — 1/1 plan (completed 2026-02-28)
- [x] **Phase 6: Extensibility Registries** — 8/8 plans (completed 2026-03-01)
- [x] **Phase 7: Hardening and Sandboxing** — 4/4 plans (completed 2026-03-01)
- [x] **Phase 8: Observability** — 4/4 plans (completed 2026-03-01)
- [x] **Phase 9: Tech Debt Code Fixes** (INSERTED) — 2/2 plans (completed 2026-03-01)
- [x] **Phase 10: Optional Tech Debt Closure** (INSERTED) — 2/2 plans (completed 2026-03-02)

Full phase details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

<details>
<summary>✅ v1.2 Developer Experience (Phases 11–14) — SHIPPED 2026-03-04</summary>

- [x] **Phase 11: Infrastructure and Debt** — 2/2 plans (completed 2026-03-02)
- [x] **Phase 12: Unified Admin Desk** — 2/2 plans (completed 2026-03-03)
- [x] **Phase 13: Local Auth** — 2/2 plans (completed 2026-03-03)
- [x] **Phase 14: Ecosystem Capabilities** — 5/5 plans (completed 2026-03-04)

Full phase details: `.planning/milestones/v1.2-ROADMAP.md`

</details>

### v1.3 Production Readiness & Skill Platform (In Progress)

**Milestone Goal:** Transform Blitz AgentOS from a feature-complete development platform into a production-ready, extensible agentic OS with proper session management, unified navigation, configurable identity, performance optimization, and a standards-compliant skill ecosystem.

**Phase Numbering:** Integer phases (15, 16, 17...): Planned milestone work. Decimal phases (15.1, 15.2): Urgent insertions if needed.

**Two tracks:**
- Track 1 — Foundations: Phases 15-18 (auth, UX, performance, identity)
- Track 2 — Skill Platform: Phases 19-23 (standards, catalog, security, marketplace, builder)

- [x] **Phase 15: Session & Auth Hardening** — Protected routes, secure cookies, session lifecycle, CVE mitigation (completed 2026-03-05)
- [x] **Phase 16: Navigation & User Experience** — Nav rail, profile page, user preferences, settings reorg (completed 2026-03-05)
- [x] **Phase 17: Performance & Embedding Sidecar** — Embedding sidecar extraction, instrumentation, bottleneck fixes (completed 2026-03-05)
- [x] **Phase 18: Identity Configuration** — Keycloak-optional boot, admin runtime config, connection testing (completed 2026-03-06)
- [x] **Phase 19: Skill Platform A — Standards Compliance** — Agent Skills spec compliance, schema extension, import/export (completed 2026-03-07)
- [x] **Phase 20: Skill Platform B — Discovery & Catalog** — FTS catalog, tool search, external registry browse, one-click import (completed 2026-03-07)
- [ ] **Phase 21: Skill Platform C — Dependency & Security Hardening** — Dependency enforcement, allowed-tools gate, update checker, scanner enhancement
- [ ] **Phase 22: Skill Platform D — Sharing & Marketplace** — Promoted skills, export download, user-to-user sharing
- [ ] **Phase 23: Skill Platform E — Enhanced Builder** — Executable skill generation, external learning, security gate on all artifacts

## Phase Details

### Phase 15: Session & Auth Hardening
**Goal**: Users have a secure, production-grade session lifecycle — unauthenticated access is impossible, sessions refresh silently, and logout works reliably
**Depends on**: Phase 14 (v1.2 complete)
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06, AUTH-07
**Success Criteria** (what must be TRUE):
  1. Visiting any authenticated page (`/chat`, `/admin`, `/canvas`, `/profile`, `/workflows`, `/skills`, `/settings`) without a valid session redirects the user to `/login`
  2. A user's session stays alive for a full work day without manual re-login — silent refresh renews the token transparently before expiry
  3. Clicking "Sign Out" clears all auth state and returns the user to `/login` — refreshing the page after logout does not restore the session
  4. An expired or revoked session (e.g., backend restart, Keycloak token revocation) automatically redirects the user to `/login` with no broken UI state
  5. Next.js is confirmed at version 15.2.3+ before any middleware ships (CVE-2025-29927 mitigation verified)
**Plans**: 3 plans (2 complete + 1 gap closure)

Plans:
- [x] 15-01: Middleware route protection, jose installation, cookie hardening, CVE verification, per-page auth removal
- [x] 15-02: Session refresh upgrade (5-min buffer), Keycloak end-session logout, session error detection, callbackUrl support
- [x] 15-03: UAT gap closure — middleware secret fix, sign-out button wiring, session expiry detection, multi-tab sync

### Phase 16: Navigation & User Experience
**Goal**: Users can navigate the entire application from a persistent navigation rail and manage their profile and preferences from a dedicated page
**Depends on**: Phase 15
**Requirements**: NAV-01, NAV-02, NAV-03, NAV-04, NAV-05, NAV-06, NAV-07, NAV-08, NAV-09, NAV-10
**Success Criteria** (what must be TRUE):
  1. A vertical navigation rail with icons for Chat, Workflows, Skills, Settings, Admin, and Profile is visible on every authenticated page — clicking any icon navigates to that section
  2. The Admin nav item is visible only to users with `admin`, `developer`, or `it-admin` roles — other users do not see it
  3. User can view their profile at `/profile` showing name, email, auth provider (SSO or Local), roles, and current session expiry — local users can change their password from this page
  4. User can set LLM thinking mode (on/off) and response style (concise/detailed/conversational) from the profile page — preferences are reflected in the next agent conversation
  5. The `/login` page and API routes are excluded from the navigation rail layout
**Plans**: 3 plans

Plans:
- [ ] 16-01-PLAN.md — Backend user_preferences model, migration 020, and GET/PUT API endpoints
- [ ] 16-02-PLAN.md — Navigation rail, mobile tab bar, and (authenticated) route group restructuring
- [ ] 16-03-PLAN.md — Profile page with account info, password change, custom instructions, LLM preferences, and agent prompt injection

### Phase 17: Performance & Embedding Sidecar
**Goal**: Memory search and agent invocations are fast by default — embedding runs in a dedicated sidecar, critical paths are instrumented, and known bottlenecks are eliminated
**Depends on**: Phase 15 (auth stable; architecturally independent of Phase 16 — can parallelize)
**Requirements**: PERF-01, PERF-02, PERF-03, PERF-04, PERF-05, PERF-06, PERF-07, PERF-08, PERF-09, PERF-10, PERF-11, PERF-12, PERF-13
**Success Criteria** (what must be TRUE):
  1. The embedding sidecar Docker service starts with bge-m3 pre-loaded, responds to health checks with model name and dimension, and serves embedding requests via HTTP — the backend no longer loads FlagEmbedding in-process
  2. Memory search during agent conversations completes without the 10-15 second cold-start delay that existed with in-process embedding — sidecar keeps the model warm
  3. `duration_ms` is logged for all 7 critical paths (memory search, tool execution, LLM call, canvas compile, MCP call, channel delivery, workflow run) and visible in structured logs
  4. Admin can trigger a full memory reindex via `POST /api/admin/memory/reindex` with confirmation — the operation re-embeds all facts and episodes from source text
  5. A single DB session per request replaces the previous 6-9 separate session opens, and Tool ACL / episode threshold / user instructions queries are cached with TTL
**Plans**: 4 plans

Plans:
- [ ] 17-01-PLAN.md — Embedding sidecar Docker service, SidecarEmbeddingProvider, BGE_M3 uvicorn removal, dimension validation, reindex API endpoint
- [ ] 17-02-PLAN.md — timed() context manager for 7 critical paths, RequestSessionMiddleware single DB session per request
- [ ] 17-03-PLAN.md — TTL caches for Tool ACL, episode threshold, user instructions; JWKS asyncio.Lock; useSkills() hoist
- [ ] 17-04-PLAN.md — Admin Memory tab UI with reindex button and confirmation dialog (PERF-05 frontend)

### Phase 18: Identity Configuration
**Goal**: Keycloak is an optional, runtime-configurable identity provider — the platform boots and works with local auth alone, and admins can enable/disable SSO from the UI without restarts
**Depends on**: Phase 15 (session hardening must be stable before touching auth config)
**Requirements**: IDCFG-01, IDCFG-02, IDCFG-03, IDCFG-04, IDCFG-05, IDCFG-06, IDCFG-07, IDCFG-08
**Success Criteria** (what must be TRUE):
  1. The backend starts successfully and serves local auth login when no Keycloak configuration exists — the health endpoint reports `{"auth": "local-only"}`
  2. The login page shows "Sign in with SSO" only when Keycloak is configured and enabled — without it, only local credentials login is available
  3. Admin can configure Keycloak connection (Issuer URL, Client ID, Client Secret, Realm, CA cert path) from the admin UI Identity tab and test the connection before saving
  4. After saving Keycloak config, SSO login works immediately without a backend restart — JWKS is reloaded from the new configuration
  5. Admin can disable SSO via a "Disable SSO" button with confirmation, reverting the platform to local-only auth
**Plans**: TBD

Plans:
- [ ] 18-01: TBD
- [ ] 18-02: TBD

### Phase 19: Skill Platform A — Standards Compliance
**Goal**: Skills created, imported, and exported by Blitz AgentOS conform to the agentskills.io specification — names are validated, metadata is complete, and bundles are structurally correct
**Depends on**: Phase 16 (skill pages accessible via nav rail)
**Requirements**: SKSTD-01, SKSTD-02, SKSTD-03, SKSTD-04, SKSTD-05
**Success Criteria** (what must be TRUE):
  1. Creating a skill with an invalid name (spaces, uppercase, consecutive hyphens, >64 chars) is rejected at creation time with a clear error message
  2. Skill metadata fields (license, compatibility, allowed_tools, tags, category, source_url) are stored in the database and visible when viewing a skill's details
  3. Importing a SKILL.md file parses all standard frontmatter fields and populates the corresponding database columns
  4. Exporting a skill produces an agentskills.io-compliant ZIP containing SKILL.md, MANIFEST.json, and an assets directory
  5. Importing a ZIP bundle validates the expected structure (SKILL.md + MANIFEST.json + assets) before processing
**Plans**: TBD

Plans:
- [x] 19-01: Standards Compliance — 7 metadata columns, name validation, SKILL.md import/export, ZIP bundle, admin UI metadata panel

### Phase 20: Skill Platform B — Discovery & Catalog
**Goal**: Users and admins can discover skills through a searchable catalog with full-text search, category filtering, and one-click import from external registries
**Depends on**: Phase 19 (spec-compliant schema required for catalog display)
**Requirements**: SKCAT-01, SKCAT-02, SKCAT-03, SKCAT-04, SKCAT-05
**Success Criteria** (what must be TRUE):
  1. The skill catalog page provides search by name/description (PostgreSQL tsvector FTS with `'simple'` language config for Vietnamese support), filter by category/status/author, and sort by date/usage
  2. Tool catalog search and filtering by handler_type, status, and name works from the admin UI
  3. Admin can browse external skill registries from configured registry URLs with paginated results and see skill details before importing
  4. One-click import from external registry triggers the existing SecurityScanner + quarantine flow — imported skills appear in `pending_review` status
**Plans**: 4 plans

Plans:
- [ ] 20-01-PLAN.md — DB migration 023: usage_count column + tsvector GIN index on skill_definitions
- [ ] 20-02-PLAN.md — Backend FTS + filter + sort params on admin_skills, user_skills, admin_tools; limit + cursor pagination on browse
- [ ] 20-03-PLAN.md — User /skills catalog page + admin skills FTS filter bar + admin tools name/handler_type filter bar
- [ ] 20-04-PLAN.md — SkillStoreBrowse detail drawer + Load More pagination + usage_count increment on skill run

### Phase 21: Skill Platform C — Dependency & Security Hardening
**Goal**: Skills with scripts declare their dependencies explicitly, tool access is restricted to declared permissions, and imported skills are monitored for upstream changes
**Depends on**: Phase 19 (allowed_tools column and spec compliance required), Phase 20 (SecurityScanner integration point for imports)
**Requirements**: SKSEC-01, SKSEC-02, SKSEC-03, SKSEC-04
**Success Criteria** (what must be TRUE):
  1. Skills with a `scripts/` directory that use undeclared subprocess, socket, or os.system calls are blocked by SecurityScanner with a specific rejection reason
  2. When a skill executes, tool calls are restricted to the intersection of the skill's declared `allowed-tools` and the user's ACL — denied calls are logged to the audit trail
  3. The update checker (Celery periodic task) detects when a skill's source URL content has changed and creates a `pending_review` version for admin approval
  4. SecurityScanner includes dependency risk factor (20%) and data flow analysis factor in its trust score calculation
**Plans**: TBD

Plans:
- [ ] 21-01: TBD
- [ ] 21-02: TBD

### Phase 22: Skill Platform D — Sharing & Marketplace
**Goal**: Skills can be promoted for visibility, exported for sharing, and shared between users within the platform
**Depends on**: Phase 20 (catalog UI exists for promotion display and export action)
**Requirements**: SKMKT-01, SKMKT-02, SKMKT-03
**Success Criteria** (what must be TRUE):
  1. Admin can mark skills as "Promoted" in the catalog — promoted skills appear in a curated section visible to all users
  2. Users can download a skill as an agentskills.io-compliant ZIP directly from the catalog UI
  3. Skills can be shared between users via the existing `artifact_permissions` system — shared skills appear in the recipient's catalog view
**Plans**: TBD

Plans:
- [ ] 22-01: TBD

### Phase 23: Skill Platform E — Enhanced Builder
**Goal**: The artifact builder generates executable skill definitions, learns from external examples, and enforces security review on every artifact before activation
**Depends on**: Phase 19 (spec compliance for generated output), Phase 21 (SecurityScanner enhancements for the security gate)
**Requirements**: SKBLD-01, SKBLD-02, SKBLD-03, SKBLD-04, SKBLD-05, SKBLD-06, SKBLD-07, SKBLD-08
**Success Criteria** (what must be TRUE):
  1. Builder generates complete `procedure_json` for procedural skills and `instruction_markdown` for instructional skills — output conforms to Agent Skills format
  2. For tool artifacts, builder generates Python handler code scaffolding with Pydantic I/O models
  3. Builder searches cached external repo indexes and shows top 3-5 relevant similar skills as reference — user can fork an existing external skill as a starting point
  4. Every artifact (built, imported, forked, or cloned) goes through SecurityScanner before activation — a SecurityReportCard A2UI component shows trust score, factor breakdown, tool permissions, injection warnings, and recommendation
  5. For `review` or `reject` recommendations from SecurityScanner, admin must explicitly approve before the skill is activated — no automatic activation for flagged artifacts
**Plans**: TBD

Plans:
- [ ] 23-01: TBD
- [ ] 23-02: TBD
- [ ] 23-03: TBD

## Progress

**Execution Order:** 1 → 2 → 2.1 → 3 → 3.1 → 4 → 4.1 → 5 → 5.1 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17 → 18 → 19 → 20 → 21 → 22 → 23

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1. Identity & Skeleton | v1.0 | 4/4 | ✅ Complete | 2026-02-24 |
| 2. Agent Core & Chat | v1.0 | 5/5 | ✅ Complete | 2026-02-25 |
| 2.1. Tech Debt Cleanup | v1.0 | 1/1 | ✅ Complete | 2026-02-26 |
| 3. Sub-Agents & Memory | v1.0 | 6/6 | ✅ Complete | 2026-02-26 |
| 3.1. Memory Read + MCP Hot-Reg | v1.0 | 1/1 | ✅ Complete | 2026-02-26 |
| 4. Canvas & Workflows | v1.1 | 5/5 | ✅ Complete | 2026-02-27 |
| 4.1. Phase 4 Polish | v1.1 | 1/1 | ✅ Complete | 2026-02-27 |
| 5. Scheduler & Channels | v1.1 | 6/6 | ✅ Complete | 2026-02-28 |
| 5.1. Workflow Execution Wiring | v1.1 | 1/1 | ✅ Complete | 2026-02-28 |
| 6. Extensibility Registries | v1.1 | 8/8 | ✅ Complete | 2026-03-01 |
| 7. Hardening & Sandboxing | v1.1 | 4/4 | ✅ Complete | 2026-03-01 |
| 8. Observability | v1.1 | 4/4 | ✅ Complete | 2026-03-01 |
| 9. Tech Debt Code Fixes | v1.1 | 2/2 | ✅ Complete | 2026-03-01 |
| 10. Optional Tech Debt Closure | v1.1 | 2/2 | ✅ Complete | 2026-03-02 |
| 11. Infrastructure & Debt | v1.2 | 2/2 | ✅ Complete | 2026-03-02 |
| 12. Unified Admin Desk | v1.2 | 2/2 | ✅ Complete | 2026-03-03 |
| 13. Local Auth | v1.2 | 2/2 | ✅ Complete | 2026-03-03 |
| 14. Ecosystem Capabilities | v1.2 | 5/5 | ✅ Complete | 2026-03-04 |
| 15. Session & Auth Hardening | v1.3 | 3/3 | ✅ Complete | 2026-03-05 |
| 16. Navigation & UX | 3/3 | Complete    | 2026-03-05 | - |
| 17. Performance & Embedding Sidecar | 7/7 | Complete    | 2026-03-05 | - |
| 18. Identity Configuration | 3/3 | Complete    | 2026-03-06 | - |
| 19. Skill Platform A — Standards | v1.3 | 1/1 | ✅ Complete | 2026-03-07 |
| 20. Skill Platform B — Catalog | 4/4 | Complete   | 2026-03-07 | - |
| 21. Skill Platform C — Security | v1.3 | 0/TBD | Not started | - |
| 22. Skill Platform D — Sharing | v1.3 | 0/TBD | Not started | - |
| 23. Skill Platform E — Builder | v1.3 | 0/TBD | Not started | - |
