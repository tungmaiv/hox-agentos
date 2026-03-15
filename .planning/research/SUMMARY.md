# Project Research Summary

**Project:** Blitz AgentOS v1.4 — Platform Enhancement & Infrastructure
**Domain:** Enterprise on-premise Agentic Operating System (platform hardening milestone)
**Researched:** 2026-03-15
**Confidence:** HIGH

---

## Executive Summary

Blitz AgentOS v1.4 is a platform hardening and enhancement milestone for an existing, shipped enterprise agentic OS. Unlike prior milestones that built core agent capabilities, v1.4 adds nine cross-cutting enhancements: SSO resilience, admin registry editing, runtime permission escalation, multi-agent tab UI, dark theme, unified dashboard, file storage, scheduler UI, and email integration. Research confirms the existing 5-layer architecture (Frontend, Security Runtime, Agent Orchestration, Tools/Memory, Infrastructure) accommodates all nine features without structural changes — only two new Docker services are required: MinIO for object storage and an email sidecar for IMAP/SMTP handling.

The recommended build order is strictly dependency-driven. Keycloak SSO hardening and admin registry edit ship first as independent, low-risk improvements. Runtime permission approval follows because it modifies Gate 3 (the security core) and must stabilize before adding more agent types. Scheduler UI, multi-agent tab architecture, UX enhancement, and unified dashboard form a parallel middle tier. Storage service and email system are last because they carry the highest infrastructure complexity and the longest external dependencies (MinIO setup, Google/Microsoft OAuth app registration). The suggested six-phase structure matches the dependency graph from ARCHITECTURE.md and the priority tiers from FEATURES.md.

The biggest risks are cross-cutting rather than feature-specific: Alembic migration branch explosions from parallel feature development (the project has already hit this pattern twice), WebSocket authentication gaps that could expose real-time system metrics, CopilotKit multi-instance context bleeding between agent tabs, and OAuth email token refresh failures that silently break email integrations. Each has a concrete mitigation detailed in the pitfalls section below.

---

## Key Findings

### Recommended Stack

The v1.4 stack additions are minimal by design. The primary frontend additions are `recharts` (dashboard charts, ~50KB gzipped — preferred over `@tremor/react`'s 200KB+ bundle given the existing shadcn/ui design system; Tremor is built on Recharts anyway), `next-themes` (dark mode without SSR flash via pre-hydration script injection), and `cronstrue` (human-readable cron expression display, pairs with the existing `croniter` backend library). The only new backend PyPI package for the main service is `minio` (Python SDK for the storage service). The email sidecar is a new Docker service with its own `pyproject.toml` using `aiosmtplib`, `aioimaplib`, `google-auth-oauthlib`, and `msal`. All other v1.4 features — WebSocket real-time feeds, circuit breaker, cron builder UI, permission approval — use libraries already in the stack (`tenacity`, native FastAPI WebSocket, shadcn/ui form primitives, existing PostgreSQL).

**Core technology additions:**
- `recharts` ^2.15.x: Dashboard charts — preferred over Tremor (lighter bundle, matches existing shadcn/ui design system, tree-shakeable)
- `next-themes` ^0.4.x: Dark/light/system theme switching — zero-flash via pre-hydration blocking script injection; localStorage + cookie persistence
- `cronstrue` ^2.x: Cron expression human-readable display — lightweight, no dependencies; pairs with existing `croniter` backend
- `minio` >=7.2.20: Python SDK for MinIO object storage — official SDK, presigned URL pattern; wrap in `asyncio.to_thread()` for async contexts
- MinIO Docker service (pin to dated release, NOT `:latest`): S3-compatible storage — single container; reassign console to port 9101 to avoid conflict with Telegram gateway at 9001
- `aiosmtplib` >=5.1.0 + `aioimaplib` >=2.0.1: Async email sending/receiving for email sidecar
- `google-auth-oauthlib` >=1.3.0 + `msal` >=1.34.0: Gmail and Microsoft 365 OAuth — mandatory since Google disabled basic auth March 2025

**What NOT to add:** `@tremor/react` (200KB+ bundle), `pybreaker`/`circuitbreaker` (new dep for a 60-line pattern), `socket.io`/`python-socketio` (native FastAPI WebSocket is sufficient), `boto3`/`aiobotocore` (MinIO has its own SDK), `react-js-cron` (Ant Design dependency), CSS-in-JS libraries, `imaplib`/`smtplib` (stdlib, synchronous, blocks event loop).

**Frontend install (v1.4 additions only):**
```
pnpm add recharts next-themes cronstrue
```

**Backend install (v1.4 additions only):**
```
uv add minio   # main service
# email sidecar: uv add aiosmtplib aioimaplib google-auth-oauthlib msal fastapi uvicorn httpx jinja2 structlog
```

### Expected Features

**Must have (table stakes — block user workflows without them):**
- Circuit breaker (CLOSED/OPEN/HALF-OPEN) with graceful Keycloak degradation to local auth — prevents cascading failure during SSO outages
- Admin edit forms for all registry artifact types (agents, tools, MCP servers) — admins cannot iterate on registrations without edit capability
- MCP server connection test button — "is this reachable?" is always the first post-registration question
- Permission request queue with admin approval/deny UI — required for HITL security escalation
- Temporal ACL with configurable expiry — "approve for 1 hour" is standard enterprise IAM; permanent-only grants are a security anti-pattern
- Dark theme with system preference detection and zero SSR flash — table stakes for modern enterprise web apps
- Avatar upload with backend validation — reject SVG (XSS risk), max 2MB, re-encode to WebP server-side
- Scheduler global dashboard with execution history, enable/disable toggle, and "run now" — Celery backend exists, needs management UI
- Visual cron expression builder with next-run preview — cron syntax is not human-readable; `0 9 * * 1` is not "every Monday at 9am" to most users
- Mission Control: active agents, running workflows, pending approvals — core operational visibility question is "what is happening right now?"
- S3-compatible object storage with presigned URLs and per-user file isolation
- Email fetch/send/reply as real agent tools (replacing mock data) with OAuth 2.0 for Google and Microsoft

**Should have (differentiators):**
- Auto-approve rules for low-risk tool+role combinations — reduces admin burden for routine permission requests
- Agent-initiated permission escalation (agent detects deny, creates request, surfaces status to user)
- Tabbed multi-agent wizard with isolated `tool_builder` and `mcp_builder` agents alongside existing `artifact_builder`
- Real-time WebSocket activity feed on dashboard with Recharts analytics charts
- Timezone-aware display on scheduler, audit logs, and execution history
- Proactive OAuth token refresh (Celery task refreshing credentials 30 minutes before expiry)
- `StorageAdapter` Protocol interface — enables future migration from MinIO to Garage/RustFS/AWS S3 without code changes

**Defer to v1.5+:**
- Full file manager UI (folder tree, drag-drop) — storage service is infrastructure; file manager is a Projects/Spaces product feature
- Unlimited simultaneous agent tabs — cap at 5-8; beyond that is resource explosion at 100-user scale
- IMAP IDLE push-based email — polling every 5 minutes is sufficient at 100 users; IDLE connections are fragile
- Custom SMTP relay — send via provider API (Gmail API / Graph API) which handles DKIM/SPF deliverability
- Calendar view of scheduled jobs — sortable table with next-run column is more practical; calendar becomes unreadable with overlapping jobs
- Custom accent colors / full theme customization — light + dark covers 99% of enterprise needs

### Architecture Approach

All nine features extend the existing 5-layer architecture without introducing new patterns or layers. The security layer gains a `CircuitBreaker` class and `PermissionRequestService`. The agent orchestration layer gains two new LangGraph graphs (`tool_builder`, `mcp_builder`). The tools/memory layer gains a `StorageAdapter` (Protocol-based, matching the existing `ChannelAdapter` pattern). Infrastructure adds MinIO and an email sidecar Docker service. Storage routes integrate into the main backend under `/api/storage/*` — NOT a separate service (port 8001 is already occupied by MCP CRM).

The current two active Alembic heads (`617b296e937a` + `83f730920f5a`) must be merged as migration `031` before any v1.4 schema work begins. This is the single most critical technical prerequisite.

**Major new components and responsibilities:**
1. `CircuitBreaker` — wraps JWKS fetch in `security/jwt.py`; state persisted to Redis for survival across backend restarts and workers
2. `PermissionRequestService` + `AutoApproveEngine` — Gate 3 escalation path; creates `permission_requests` and evaluates `auto_approve_rules` tables; LangGraph interrupt on escalation
3. `DashboardWebSocketManager` — FastAPI native WebSocket at `/ws/dashboard`; Redis Pub/Sub for cross-worker broadcast; dedicated `get_ws_current_user()` dependency (not the HTTP `Depends()` pattern)
4. `StorageAdapter` Protocol + `MinIOStorageAdapter` — routes at `/api/storage/*` in main backend; 5 new tables (`files`, `folders`, `file_folder_links`, `file_shares`, `memory_file_links`)
5. Email sidecar (Python, port 8003) — IMAP/SMTP with XOAUTH2, forwards incoming mail to backend via existing `POST /api/channels/incoming` pattern
6. `ToolBuilderAgent` + `MCPBuilderAgent` — new LangGraph graphs; single CopilotKit provider with `key={tab.sessionId}` tab-switching (never multiple simultaneous providers)

**New DB tables (7-8 total):** `permission_requests`, `auto_approve_rules`, `agent_dependencies`, `files`, `folders`, `file_folder_links`, `file_shares`, `memory_file_links`
**Modified tables:** `tool_acl` (add `duration_type`, `expires_at`, `granted_at`, `granted_by`), `user_preferences` (add `theme`, `timezone`, `avatar_url`)

### Critical Pitfalls

1. **Alembic migration branch explosion** — Nine features developed on parallel branches each create migrations from the same head. The project has already hit this twice. Prevention: assign migration number ranges per feature before development starts (e.g., 031-032 Keycloak/Security, 033 agent deps, 034 UX, 035 storage, 036 email); enforce "one feature holds the migration lock at a time"; run `alembic heads` in CI to fail builds with multiple heads.

2. **WebSocket authentication bypass and connection leak** — FastAPI `Depends()` does not work the same way for WebSocket; JWT in query parameters ends up in server and proxy logs; long-lived connections outlive JWT expiry without re-validation. Prevention: dedicated `get_ws_current_user()` dependency extracting JWT from query param at handshake only; 60-second heartbeat re-validates JWT; WebSocket ticket pattern (short-lived single-use ticket from REST endpoint); per-user connection limit enforced via Redis.

3. **CopilotKit multi-instance context bleeding** — Multiple `<CopilotKit>` providers on the same page cause message state leakage between agent tabs (documented GitHub issue #1159). Prevention: single CopilotKit provider with `key={tab.sessionId}` tab-switching; only mount the active tab's agent; never render multiple providers simultaneously; consider "one active builder at a time" UX constraint as simpler fallback.

4. **OAuth email token refresh failure** — Google disabled basic auth March 2025; OAuth tokens expire (1 hour for Google); failed refresh silently breaks email integration with no user notification. Prevention: `last_refreshed_at` + `expires_at` on `user_credentials`; Celery periodic task refreshing tokens 30 minutes before expiry; structured error "Your email connection has expired, please re-authenticate" returned to agent instead of runtime crash.

5. **MinIO Docker image pin and credential initialization race** — `minio/minio:latest` is frozen at October 2025 with unpatched CVEs (CVE-2025-62506); fresh containers may ignore env credentials before initialization completes. Prevention: pin to a specific dated release (e.g., `quay.io/minio/minio:RELEASE.2025-01-10T21-58-47Z`); named Docker volume (not bind mount); init script gated on `service_healthy`; `depends_on: condition: service_healthy` in backend service definition.

---

## Implications for Roadmap

Based on research, six phases are recommended. Phases 3 and 4 have parallel tracks that can execute concurrently.

### Phase 1: Foundation Hardening
**Rationale:** Two independent, low-risk, high-impact admin improvements that each have zero dependencies on other v1.4 features. Keycloak hardening stabilizes the auth layer before any feature that touches auth. Registry edit fills the most obvious gap in admin daily workflow. Both can run as parallel tracks within the phase.
**Delivers:** Circuit-broken Keycloak with CLOSED/OPEN/HALF-OPEN health categorization visible in admin Identity tab; edit + connection-test forms for all registry artifact types (agents, tools, MCP servers)
**Addresses:** Keycloak SSO Hardening (#07), Admin Registry Edit UI (#06)
**Avoids:** Pitfall 7 (circuit breaker state lost on restart — store in Redis; read on startup), Pitfall 15 (MCP test timeout freezes UI — strict 5-second timeout; background task pattern returning `test_id`)
**Research flag:** Standard patterns. Circuit breaker is a well-documented 60-line state machine. Registry edit is CRUD on existing tables. Skip phase research.

### Phase 2: Security Enhancement
**Rationale:** Modifies Gate 3 — the security core. Must be stable and tested in isolation before adding new agent types (Phase 3 Track 2) that will trigger permission escalation checks. This is the only v1.4 feature that directly mutates the security pipeline.
**Delivers:** Permission request queue with admin approval/reject UI; temporal ACL with expiry on `tool_acl`; `auto_approve_rules` for low-risk tool+role combinations; LangGraph interrupt on permission escalation; in-app notification of approval/denial outcome
**Uses:** Existing 3-gate security layer; `tool_acl` table extension; new `permission_requests` + `auto_approve_rules` tables (migrations 032-033 after 031 merge)
**Addresses:** Runtime Permission Approval HITL (#01)
**Avoids:** Pitfall 8 (temporal ACL never expires — add `AND (expires_at IS NULL OR expires_at > NOW())` to `check_tool_acl()` query; hourly Celery cleanup task), Pitfall 14 (queue flooding from scheduled workflows — deduplicate pending requests per `user_id + tool_name`)
**Research flag:** Standard patterns. LangGraph interrupt is an existing codebase pattern (existing HITL workflows use it). Skip phase research.

### Phase 3: Core Features (Two Parallel Tracks)
**Rationale:** Independent features with no overlap. Track 1 is purely UI on the existing Celery/workflow backend. Track 2 is agent architecture plus frontend tab refactoring. Neither blocks the other.
**Track 1 delivers:** Scheduler global dashboard at `/admin/scheduler`, visual cron builder with `cronstrue` display, execution history with live status, enable/disable toggle per job, "run now" button, timezone-aware display
**Track 2 delivers:** `tool_builder` and `mcp_builder` LangGraph agents; tabbed artifact wizard with single CopilotKit provider + `key={tab.sessionId}` tab-switching; `agent_dependencies` table for cross-tab artifact linking
**Uses:** `cronstrue` (frontend); existing `croniter` (backend cron validation); existing `langgraph`; existing CopilotKit (single provider — never multiple simultaneous)
**Addresses:** Scheduler UI (#15), Multi-Agent Tab Architecture (#16)
**Avoids:** Pitfall 10 (build scheduler backend APIs before UI — reuse `POST /api/workflows/{id}/run` for run-now; run Celery inspect in `asyncio.to_thread()` to avoid event loop blocking), Pitfall 4 (single CopilotKit provider with tab-switching — never multiple providers)
**Research flag:** Scheduler UI is standard patterns. Multi-Agent Tab needs a spike before planning: verify CopilotKit v1.50+ `useAgent` hook compatibility with existing `LangGraphAGUIAgent`, venv patches in `.venv/lib/python3.12/site-packages/copilotkit/__init__.py`, and runtime.py AG-UI dispatch. Have a fallback design ready: "one active builder at a time" UX constraint avoids the multi-instance problem entirely.

### Phase 4: Experience and Visibility (Two Parallel Tracks)
**Rationale:** Polish and operational visibility. Dashboard benefits from having scheduler data (Phase 3) and permission events (Phase 2) to display. UX enhancement is additive and independent. Both tracks can ship without each other.
**Track 1 delivers:** Dark/light/system theme with zero SSR flash via `next-themes`; timezone picker stored in `user_preferences`; timezone-aware display on all timestamps; avatar upload (local filesystem initially — migrated to MinIO in Phase 5)
**Track 2 delivers:** Mission Control dashboard at `/dashboard` with real-time WebSocket feed; Recharts analytics (AreaChart for trends, BarChart for LLM cost, LineChart for latency, PieChart for agent success rate); quick actions and deep-link to Grafana for technical metrics
**Uses:** `next-themes` ^0.4.x; `recharts` ^2.15.x (with `next/dynamic` + `ssr: false` wrappers); native FastAPI WebSocket; Redis Pub/Sub for broadcast; `user_preferences` table additions
**Addresses:** UX Enhancement (#13), Unified Dashboard (#08+#14)
**Avoids:** Pitfall 6 (dark theme FOUC — `next-themes` blocking script injection before hydration), Pitfall 9 (Recharts breaks SSR — wrap all chart components in `next/dynamic` with `ssr: false`), Pitfall 2 (WebSocket auth bypass — dedicated `get_ws_current_user()`, 60s heartbeat re-validation, Redis per-user connection limit), Pitfall 12 (WebSocket blocks event loop — Redis Pub/Sub for broadcasting; `asyncio.create_task()` for all broadcast calls)
**Research flag:** Dark theme with `next-themes` is the canonical Next.js 15 solution; skip research. WebSocket + Redis Pub/Sub is well-documented but new to this codebase — verify FastAPI WebSocket auth approach in an isolated spike before full dashboard build.

### Phase 5: Infrastructure
**Rationale:** Largest infrastructure addition (new Docker service, 5 new tables, storage adapter, file API). Separate phase contains blast radius. Avatar upload in Phase 4 starts with local filesystem and migrates storage path to MinIO when this phase ships.
**Delivers:** MinIO Docker service (pinned image, named volume, init script, `service_healthy` healthcheck); `StorageAdapter` Protocol + `MinIOStorageAdapter`; file/folder CRUD under `/api/storage/*` in main backend; per-user isolation (`WHERE owner_id = $1`); presigned upload/download URLs; avatar path migration from local filesystem to MinIO
**Uses:** `minio` >=7.2.20 Python SDK; new `files`/`folders`/`file_folder_links`/`file_shares`/`memory_file_links` tables (migration 035)
**Addresses:** Storage Service (#19)
**Avoids:** Pitfall 3 (pin MinIO to dated release, not `:latest`; named volume; `service_healthy` condition in backend `depends_on`), Pitfall 11 (MinIO console port 9001 conflicts with Telegram gateway — reassign MinIO console to port 9101; optionally do not expose console port to host at all since backend accesses MinIO via Docker network)
**Research flag:** MinIO integration with presigned URLs is well-documented. `StorageAdapter` Protocol follows the existing `ChannelAdapter` pattern directly. Skip phase research.

### Phase 6: Email and Notifications
**Rationale:** Requires external service registration (Google Cloud Console OAuth client, Azure AD app registration) that may take days to weeks for approval. Start registration immediately — do not wait until implementation begins. Also benefits from storage service (Phase 5 for future email attachments) and dashboard (Phase 4 for notification surfaces). Highest external dependency count of all nine features.
**Delivers:** Email sidecar Docker service (Python, port 8003); Gmail OAuth 2.0 integration (XOAUTH2 IMAP/SMTP); Microsoft 365 OAuth 2.0 integration; real email fetch/send/reply replacing mock data in `email_tools.py`; notification routing with per-event-type channel preferences; proactive Celery token refresh task
**Uses:** `aiosmtplib`, `aioimaplib`, `google-auth-oauthlib`, `msal`, `jinja2`; existing `ChannelAdapter` protocol; existing `user_credentials` AES-256 encrypted storage; existing `POST /api/channels/incoming` endpoint
**Addresses:** Email System and Notifications (#18)
**Avoids:** Pitfall 5 (proactive Celery refresh task at 30-minute-before-expiry; `expires_at` + `last_refreshed_at` on `user_credentials`; structured re-auth error to agent); IMAP IDLE anti-feature (5-minute polling is sufficient at 100 users — IDLE connections are fragile and resource-consuming)
**Research flag:** Google Cloud Console OAuth client setup for Gmail (consent screen, required scopes, app verification vs. Workspace domain-wide delegation) and Azure AD app registration must be researched before Phase 6 planning — these are administrative processes with potential approval delays, not code questions. Determine the correct OAuth path for internal-only enterprise use (service account + domain delegation may bypass public app verification entirely).

### Phase Ordering Rationale

- **Phase 1 before Phase 2:** Auth resilience must be stable before modifying the security gate itself
- **Phase 2 before Phase 3 Track 2:** Builder agents trigger permission checks — escalation path must exist before adding new agent types
- **Phase 3 Track 1 (Scheduler) before Phase 4 Track 2 (Dashboard):** Dashboard surfaces scheduler data; building dashboard before scheduler data exists makes the dashboard story incomplete
- **Phase 5 decoupled from Phase 4:** Avatar upload in Phase 4 degrades gracefully to local filesystem storage, enabling Phase 4 to ship without waiting for MinIO infrastructure
- **Phase 6 last:** Longest external dependency lead time (OAuth registration); benefits from all preceding infrastructure; email attachments naturally use Phase 5 MinIO
- **Migration 031 (Alembic head merge) is a zero-feature prerequisite** — must be committed and deployed before any Phase 1 schema work begins; without it, `alembic upgrade head` fails with "Multiple heads" error

### Research Flags

**Phases needing deeper research before planning:**
- **Phase 3 (Multi-Agent Tab):** CopilotKit upgrade from v0.1.78 to v1.50+ (for `useAgent` hook). The existing codebase has a patched `copilotkit/__init__.py` in the venv. A major version upgrade may break `LangGraphAGUIAgent` import, AG-UI SSE streaming, and runtime.py dispatch. Run a compatibility spike on an isolated branch before committing to the upgrade path. If incompatible, implement with "one active builder at a time" constraint instead.
- **Phase 6 (Email OAuth):** Determine the correct OAuth path for 100 internal users on a company Google Workspace account — service account + domain-wide delegation likely bypasses public app verification consent screen delays. Verify required scopes for Gmail (`gmail.readonly`, `gmail.send`) and Microsoft Graph (`Mail.Read`, `Mail.Send`) and whether they require verification or can run in development mode for internal enterprise use.

**Phases with standard patterns (skip research-phase):**
- **Phase 1:** Circuit breaker is a well-documented state machine; registry CRUD is standard FastAPI
- **Phase 2:** LangGraph interrupt is an existing codebase pattern from current HITL workflow nodes
- **Phase 4 (UX):** `next-themes` is the canonical Next.js dark mode solution with zero ambiguity
- **Phase 5:** MinIO + StorageAdapter Protocol follows the existing ChannelAdapter pattern exactly

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core additions verified on PyPI/npm with specific versions. Architecture decision (recharts over Tremor) backed by bundle size data and shadcn/ui compatibility evidence. Email library versions confirmed from PyPI. |
| Features | HIGH | All 9 features are well-understood enterprise patterns with cited industry references (Microsoft, AWS, Permit.io, agentskills.io). Priority tiers and anti-features are well-reasoned. |
| Architecture | HIGH | Derived from direct first-party codebase inspection, architecture.md, and enhancement specifications. Port conflict (MinIO 9001 vs Telegram gateway) identified and resolved. Alembic multi-head state documented and sequenced. |
| Pitfalls | HIGH | 5 critical + 7 moderate + 5 minor pitfalls identified. Critical ones reference specific GitHub issues, CVE numbers, and verified code patterns from v1.0-v1.3 experience. Phase-specific warning table provided. |

**Overall confidence:** HIGH

### Gaps to Address

- **CopilotKit v1.50+ upgrade compatibility:** Cannot be assessed from research alone. Needs a compatibility spike (isolated branch, upgrade venv, verify `LangGraphAGUIAgent` import path, `POST /api/copilotkit` dispatch, and AG-UI SSE streaming still work) before Phase 3 planning commits to the multi-agent tab architecture. If the upgrade breaks too much, the fallback "one active builder at a time" design is simpler and avoids the multi-instance problem entirely.

- **MinIO Community Edition maintenance trajectory:** MinIO CE entered maintenance mode (Dec 2025, no new features). The `StorageAdapter` Protocol is the hedge for future migration. Monitor Garage (Rust, CNCF sandbox) and RustFS (Apache 2.0) as S3-compatible drop-in alternatives — both are production-emerging candidates for the 100-user scale.

- **Avatar storage in Phase 4 before Phase 5 lands:** Phase 4 ships avatar upload; Phase 5 ships MinIO. Decision needed before Phase 4 planning: store avatars in local filesystem at `/data/avatars/{user_id}.webp` (Docker volume, migrate to MinIO path in Phase 5 with a one-time migration script) OR store as PostgreSQL `bytea` (simple but adds to DB size). Recommendation: local filesystem, consistent with Phase 5 MinIO migration path.

- **Google OAuth path for internal Workspace users:** For 100 internal employees on a company Google Workspace account, domain-wide delegation with a service account may bypass the public app verification process entirely. If this is the case, Phase 6 implementation is significantly simpler and faster. Confirm before Phase 6 planning.

---

## Sources

### Primary (HIGH confidence)
- `docs/architecture/architecture.md` — 5-layer architecture, component inventory (source of truth)
- `docs/enhancement/topics/*/00-specification.md` — Feature specifications for all 9 v1.4 topics
- `docs/enhancement/ANALYSIS-REPORT.md` — Cross-feature analysis and dependency graph
- `docs/dev-context.md` — Existing service ports, DB tables, API endpoints, gotchas
- `CLAUDE.md` Section 13 — Alembic migration state, test commands, critical gotchas from v1.0-v1.3
- MinIO Python SDK (v7.2.20): https://pypi.org/project/minio/
- aiosmtplib (v5.1.0): https://pypi.org/project/aiosmtplib/
- aioimaplib (v2.0.1): https://pypi.org/project/aioimaplib/
- google-auth-oauthlib (v1.3.0): https://pypi.org/project/google-auth-oauthlib/
- MSAL Python (v1.34.0): https://pypi.org/project/msal/
- FastAPI WebSocket docs: https://fastapi.tiangolo.com/advanced/websockets/
- next-themes GitHub: https://github.com/pacocoursey/next-themes
- shadcn/ui dark mode guide: https://ui.shadcn.com/docs/dark-mode/next
- Google Basic Auth sunset (March 2025): https://support.google.com/a/answer/14114704
- Circuit Breaker Pattern (Microsoft Azure): https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker
- HITL for AI Agents (Permit.io): https://www.permit.io/blog/human-in-the-loop-for-ai-agents-best-practices-frameworks-use-cases-and-demo

### Secondary (MEDIUM confidence)
- Recharts npm (v2.15.x/v3.8.0): https://www.npmjs.com/package/recharts — bundle size vs Tremor comparison
- cronstrue npm: https://www.npmjs.com/package/cronstrue — cron display library
- CopilotKit v1.50 release: https://www.copilotkit.ai/blog/copilotkit-v1-50-release-announcement-whats-new-for-agentic-ui-builders — `useAgent` hook availability
- FastAPI WebSocket JWT authentication: https://dev.to/hamurda/how-i-solved-websocket-authentication-in-fastapi-and-why-depends-wasnt-enough-1b68
- CopilotKit useCopilotChat isolation issue: https://github.com/CopilotKit/CopilotKit/issues/1159 — multi-instance context bleeding
- MinIO Docker Hub deprecation: https://github.com/minio/minio/issues/21502 — CE image freeze at October 2025
- Alembic migration conflicts: https://github.com/sqlalchemy/alembic/discussions/1543

### Tertiary (LOW confidence — needs validation during implementation)
- MinIO CE maintenance mode trajectory (Dec 2025): https://www.infoq.com/news/2025/12/minio-s3-api-alternatives/ — alternatives (Garage, RustFS) not yet production-proven in this stack
- Google OAuth app verification timeline — estimated from general knowledge; Workspace domain-wide delegation path may bypass this entirely (needs confirmation before Phase 6 planning)

---
*Research completed: 2026-03-15*
*Ready for roadmap: yes*
