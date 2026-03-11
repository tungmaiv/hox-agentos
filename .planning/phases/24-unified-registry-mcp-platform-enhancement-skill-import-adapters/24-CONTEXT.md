# Phase 24: Unified Registry, MCP Enhancement & Skill Import Adapters - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Unify all entity management (agents/skills/tools/MCP servers) into a single `registry_entries` table with a strategy-pattern backend; add stdio MCP transport support for public CLI-installed servers; build pluggable skill import adapters (SkillRepo, Claude Market, GitHub, ZIP); replace the in-process WeightedSecurityScanner with a standalone Docker security scan service (pip-audit, bandit, detect-secrets); consolidate admin UI from 14+ pages to a 4-tab layout; make LLM model/provider configurable from admin console. Tech debt cleanup (SWR build fix, CREDENTIAL_ENCRYPTION_KEY, Keycloak SSO error, page load performance) is included in 24-01.

New agent types, workflow triggers, and external channel integrations are out of scope.

</domain>

<decisions>
## Implementation Decisions

### Registry migration strategy (24-02)

- **Drop old tables:** After migrating all data to `registry_entries`, the old tables (`agent_definitions`, `skill_definitions`, `tool_definitions`, `mcp_servers`) are dropped in the same Alembic migration. Clean break — no views, no aliases, no dual sources.
- **Data migration in Alembic:** A single migration file (028) does the full cycle atomically: CREATE `registry_entries` → INSERT from each old table with type mapping → DROP old tables. No separate data scripts.
- **Single skill type, no versioning:** Merge instructional + procedural skill types into one. Latest version is the only version — editing overwrites in place. No activate/deactivate workflow. Status is simply: `active` / `draft` / `archived`.
- **Replace all API routes:** Old scattered routes (`/api/admin/skills/*`, `/api/admin/tools/*`, `/api/gateway/registry/*`, `/api/mcp/*`) are removed entirely. New unified routes at `/api/registry/*` become the only API surface. Frontend updated to use new routes.

### Admin UI tab structure (24-06)

- **4-tab layout:**
  - **Registry** — nav hub; each entity type (Agents / Skills / Tools / MCP Servers) has its own dedicated page, accessible from the Registry tab as a nav menu or dashboard with counts.
  - **Access** — Users, Permissions, Credentials.
  - **System** — Config, Identity (SSO), LLM model/provider settings, Memory management.
  - **Build** — Artifact Builder, Skill Store.
- **Registry tab is a nav hub** (not a unified list): clicking a type navigates to its dedicated page. Keeps each type's specific CRUD UI intact without cramming into one grid.
- **Memory page** moves to System tab (infrastructure concern, not user management).
- **Identity/Credentials** stay in Access tab.

### Security scan service availability (24-05)

- **Fallback to in-process scanner:** When the Docker security scan service is unavailable (down, timeout, crash), the backend falls back to the existing `SecurityScanner` in `backend/skills/security_scanner.py` (injection checks, LLM-based scoring). Skill save proceeds with lightweight scan. Log a warning with `scan_engine='fallback'`.
- **Admin-triggered retroactive scan:** No automatic re-scanning of existing active skills. Add an admin action (button in System tab or skill list) that triggers a batch re-scan on demand. Configurable by administrator — not automatic on service startup.
- **ScanResults tab in admin skill detail:** Full pip-audit and bandit output surfaces as a new "Scan Results" tab in the admin skill detail view. `SecurityReportCard` stays in the builder panel for quick-save feedback (summary score + recommendation). The Scan Results tab shows raw tool output, CVE IDs, file:line references.
- **Scan runs on every write:** New saves, imports, forks — all trigger a scan. Docker service first, fallback to in-process if unavailable.

### Tech debt scope and priority (24-01)

- **CREDENTIAL_ENCRYPTION_KEY is back in scope:** Add `CREDENTIAL_ENCRYPTION_KEY` to `backend/.env` and `core/config.py` validation. Required before any OAuth flows go live. No retroactive migration of existing credential rows — encryption applies to new writes only.
- **Priority order (if capacity is limited):**
  1. SWR/Server Component build fix — unblocks `pnpm build` and CI
  2. CREDENTIAL_ENCRYPTION_KEY — needed before OAuth
  3. Keycloak SSO "Server error — Configuration" — affects SSO login reliability
  4. Page load performance — 5-minute sign-in issue after Phase 18 changes
- **Page load fix depth:** Fix ALL 5 hypotheses from the pending todo:
  1. Aggressive caching for `get_keycloak_config()` DB reads (pre-warm on startup)
  2. `auth.ts` startup fetch — add readiness probe before fetching `/api/internal/keycloak/provider-config`
  3. NextAuth SSR waterfall — reduce per-page session resolution round-trips
  4. Cold-start retries — add backoff/timeout so LiteLLM/Keycloak not-ready doesn't cascade
  5. JWKS pre-warm — fetch JWKS at app startup, not on first auth request

### Claude's Discretion

- Exact column mapping from old tables to `registry_entries` (field naming, JSONB structure for type-specific config)
- Migration 028 numbering — confirm no conflicts with any migrations added since Phase 23
- Which of the 4 Registry tab entity pages reuses existing admin page components vs needs new ones
- `scan_engine` field name in scan result storage (`'full'` vs `'docker'` vs `'fallback'`)
- Retry/timeout policy for Docker scan service HTTP client (suggested: 10s timeout, 1 retry)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets

- `backend/skills/security_scanner.py`: `SecurityScanner.scan()` — existing Python in-process scanner. Becomes the fallback when Docker service unavailable. No changes needed to this file.
- `backend/gateway/tool_registry.py`: current ToolRegistry (DB-backed with caching) — superseded by `registry_entries` strategy handlers in 24-02. Can be removed after migration.
- `backend/mcp/registry.py`: MCPRegistry (runtime discovery) — superseded. Merge into unified registry strategy handler.
- `backend/core/models/skill_definition.py`, `agent_definition.py`, `tool_definition.py`, `mcp_server.py` — all dropped after migration 028.
- `frontend/src/components/admin/security-report-card.tsx` — existing component. Stays in builder panel. Not changed for 24-05.
- `frontend/src/app/(authenticated)/admin/` — 14 existing pages. Some can be reused under the new tab structure; Registry type pages (agents, skills, tools, mcp-servers) likely need minimal changes since they keep their dedicated pages.
- `frontend/src/components/admin/artifact-builder-client.tsx` — existing builder. Import panel (quick task 7) already added URL import. No new builder changes in Phase 24.

### Established Patterns

- `JSON().with_variant(JSONB(), 'postgresql')` for JSONB columns in ORM models.
- `status='pending_review'` quarantine pattern — continues for skills that fail full Docker scan.
- `structlog.get_logger(__name__)` + `get_audit_logger()` for scanner decisions.
- Migration chain: latest is 027 (`027_skill_repo_index.py`). Next is **028** for `registry_entries`.
- Alembic `migration chain: 001 → ... → 027 → 83f730920f5a` (hex head is platform_config). Migration 028 must merge from both heads if needed.

### Integration Points

- `backend/api/routes/` — existing `admin_skills.py`, `admin_tools.py`, `admin_agents.py`, `mcp.py` routes are replaced by `registry.py` in 24-02.
- `backend/gateway/runtime.py` — currently uses `tool_registry.get_tools_for_user()`. Must be updated to read from unified registry after 24-02.
- `infra/litellm/config.yaml` + LiteLLM `/config/update` endpoint — hot-reload support for LLM config changes from admin console in 24-06.
- `infra/security-scanner/` — new Docker service directory for 24-05. Python microservice with pip-audit, bandit, detect-secrets. Exposed as HTTP API.

</code_context>

<specifics>
## Specific Ideas

- The Registry tab should feel like a hub/dashboard: show counts per type (e.g., "12 Skills", "3 MCP Servers") with navigation buttons to each type's dedicated page. Not a flat list.
- The admin-triggered retroactive scan could live in the System tab under a "Maintenance" section — similar to the memory reindex button added in Phase 17.
- LiteLLM hot-reload: after admin saves LLM config, backend calls LiteLLM's `POST /config/update` — no container restart needed. This was called out in the pending todo and is the right approach.
- For the Keycloak SSO fix: the most likely root cause is `auth.ts` startup fetch timing out when Keycloak isn't ready yet. A readiness probe (retry with backoff) should resolve the "Server error — Configuration" error in most cases.

</specifics>

<deferred>
## Deferred Ideas

- **HashiCorp Vault for secret management** — explicitly post-MVP per CLAUDE.md; confirmed deferred.
- **Stack initialization wizard** — pending todo from 2026-03-05; separate phase.
- **Ngrok → Cloudflare Tunnel** — pending todo from 2026-03-02; separate phase.
- **Proactive similar skills auto-surface** — was deferred from Phase 23; still deferred.
- **Skill composition** — explicitly deferred to v1.4+.

</deferred>

---

*Phase: 24-unified-registry-mcp-platform-enhancement-skill-import-adapters*
*Context gathered: 2026-03-12*
