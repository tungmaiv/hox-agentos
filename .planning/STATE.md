---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Developer Experience
status: in_progress
last_updated: "2026-03-04T16:07:10Z"
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 10
  completed_plans: 10
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-02 after v1.2 roadmap)

**Core value:** Every Blitz employee gets an intelligent, context-aware assistant that automates their daily work routines and lets them build custom automations without writing code — all within an enterprise-secure, on-premise environment where data never leaves the company.
**Current focus:** v1.2 Developer Experience — Phase 14 complete (all 5 plans done)

## Current Position

Milestone: v1.2 Developer Experience
Phase: 14 of 14 (Ecosystem Capabilities) — Plan 05 complete
Status: Phase 14 Plan 05 complete — openapi_proxy dispatch branch wired, ECO-02 fully satisfied
Last activity: 2026-03-04 - Completed quick task 3: fix all tech debt from v1.2 audit

Progress: [████████████] 100% — v1.2 Phase 14 Plan 05 done (all plans complete)

## Performance Metrics

**Velocity (v1.1 baseline):**
- Total plans completed: 35 (across v1.0 + v1.1)
- Average duration: ~13 min
- Total execution time: ~3.5 hours

**Recent Trend:**
- Last 5 plans (v1.1): 3 min, 51 min, 199 min, 8 min, 4 min
- Trend: Stable (outliers are human-verify + observability stack plans)

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v1.2 Roadmap]: Phase 11 combines INFRA + DEBT — small items, same dependency level, unblocks all later phases
- [v1.2 Roadmap]: Phase 12 and Phase 13 both depend on Phase 11 but not each other — can execute in parallel if needed
- [v1.2 Roadmap]: Phase 14 depends on Phase 12 (needs unified /admin for repository management UI)
- [Phase 10-02]: Grafana contact_points.yml chatid must be hardcoded as quoted string — env-var substitution of negative integers re-parsed as YAML number
- [09-02]: get_llm() must NOT use @lru_cache — each call creates new ChatOpenAI instance with its own callback
- [11-01]: load_prompt() first parameter is prompt_name (not name) — avoids Python kwargs collision when name= is used as a template variable
- [11-01]: PromptLoader caches raw template string (not rendered output) — same template rendered fresh per call with caller-supplied vars
- [11-02]: _route_after_master in plan = _pre_route in code (renamed in Phase 6); TODO(tech-debt) comment placed on _pre_route
- [11-02]: update_agent_last_seen and serverFetch marked TODO: verify dead — no production callers but not confirmed dead (future wiring possible)
- [11-live]: docker-compose.local.yml is the canonical Docker dev override — always use `just dev-local` for full hot-reload stack; never mount ./backend:/app (overwrites .venv)
- [11-live]: Keycloak admin API for service account requires master realm password grant (admin/admin-cli) — client_credentials token has custom flat mapper that breaks resource_access.realm-management.roles format required by admin REST API
- [11-live]: KEYCLOAK_URL in backend/.env has no port (443) — Docker containers need port 7443 override in docker-compose.local.yml; keycloak.blitz.local resolves to 172.16.155.115 via Tailscale DNS
- [11-live]: delivery_router_node must receive user_id in initial_state (not only contextvar) — state.get("user_id") is the only path delivery router uses to resolve channel account for outbound
- [11-live]: format_for_channel() must be called in delivery_router.deliver() before send_outbound — without it, sub-agent JSON responses sent as raw JSON to Telegram
- [11-live]: async_session() context manager calls session.close() NOT session.rollback() — when a DB query aborts a PostgreSQL transaction, closing without ROLLBACK returns the connection dirty to the pool → InFailedSQLTransactionError on next request. Fix: wrap read-only queries with `async with session.begin():` (auto-rollback) and use explicit try/except rollback/raise for write sessions. Also fix get_db() FastAPI dependency.
- [11-live]: TELEGRAM_GATEWAY_URL in backend/.env must be docker service name when backend runs in Docker — localhost:9001 resolves inside container (nothing), not to gateway sidecar
- [11-INFRA-02]: External Cloudflare Tunnel at 172.16.155.118 is the accepted final answer — no cloudflared Docker Compose service required. Confirmed by product owner 2026-03-03. Phase 11 verification: 5/5 complete.
- [Phase 12-01]: Admin credential API returns metadata only (user_id, provider, connected_at) — token values never in response; registry:manage RBAC gate
- [Phase 12-01]: Next.js admin credential proxy uses NEXT_PUBLIC_API_URL not BACKEND_INTERNAL_URL — matches existing admin proxy pattern in config/route.ts
- [Phase 12-01]: /settings/agents and /settings/integrations kept as files (not deleted) — Server Component redirect() returns HTTP redirect not 404; /settings stripped of Admin section
- [Phase 12]: [12-02]: fill_form co-agent tool added to artifact_builder — AI can now update form fields live via copilotkit_emit_state
- [Phase 12]: [12-02]: check-name endpoints declared BEFORE /{id} routes in all 4 admin route files to prevent FastAPI routing collision
- [Phase 13-01]: [13-01]: Replace passlib with direct bcrypt — passlib 1.7.4 incompatible with bcrypt 5.x (detect_wrap_bug rejects 256-byte test password)
- [Phase 13-01]: [13-01]: validate_local_token takes AsyncSession param — reuses request-scoped DB session for is_active check in get_current_user
- [Phase 13-02]: [13-02]: Credentials provider authorize() calls backend directly from server side — token proxy route is supplementary only
- [Phase 13-02]: [13-02]: Local token expiry uses error="SessionExpired" to distinguish from Keycloak "RefreshAccessTokenError" on login page
- [Phase 13-02]: [13-02]: Admin Users page edit dialog limited to username/email/password — group/role management kept separate (KISS)
- [14-01]: CapabilitiesCard uses collapsed sections with count badges — sections collapsed by default per CONTEXT.md locked decision
- [14-01]: system.capabilities seeded into tool_definitions in migration 019 — single authoritative source, no separate seeding script
- [14-01]: Capabilities routing handled in _classify_by_keywords() before agent routing — returns 'capabilities' intent
- [14-01]: _capabilities_node routes through delivery_router like all other nodes — consistent graph topology
- [14-01]: Agents and MCP servers use default-allow; tools and skills use batch_check_artifact_permissions() filtering
- [Phase 14]: 14-04: skill_export router registered before admin_skills.router — literal /export must precede UUID /{skill_id} for correct FastAPI routing
- [Phase 14]: 14-04: admin proxy binary fix branches on Content-Type — application/zip uses arrayBuffer(), others keep text() for backward compat
- [Phase 14-02]: encrypt_token imported at module level in service.py — required for unittest.mock.patch() testability
- [Phase 14-02]: Tool registry cache now includes config_json and mcp_server_id — enables openapi_proxy dispatch without extra DB round-trips
- [Phase 14-03]: browse_skills reads cached_index from DB — no remote HTTP calls at browse time, freshness via explicit sync action
- [Phase 14-03]: User proxy routes at /api/skill-repos/* are separate files from /api/admin/[...path] catch-all — different RBAC gates (chat vs registry:manage)
- [Phase 14-03]: 2-step import dialog — confirm intent then show security score/recommendation before closing — user must see scan results
- [Phase 14-05]: openapi_proxy dispatch branch placed as elif between mcp_server and 501 fallback — preserves all existing behavior unchanged
- [Phase 14-05]: mcp_server_id from cache is str; cast to uuid.UUID() before McpServer.id query — avoids PostgreSQL type mismatch
- [Phase 14-05]: update_tool_last_seen wrapped in try/except — best-effort, never fails the tool call
- [Phase 14-05]: is_error = result.get("error") is True (strict bool check) — avoids false positives from result dicts with non-True "error" keys
- [quick-3]: admin/layout.tsx zero-roles bypass removed — both Keycloak and local-auth sessions always populate realmRoles from JWT; zero roles means no admin role
- [quick-3]: test_skill_export.py uses AsyncMock(side_effect) for async FastAPI dependency mocking — avoids unawaited coroutine RuntimeWarning from _auth_override pattern

### Pending Todos

- [ ] Start WhatsApp Business API verification process (takes 1-4 weeks, needed for future live testing)
- [ ] Add CREDENTIAL_ENCRYPTION_KEY to production .env before Phase 3 OAuth flows
- [ ] [TECH DEBT] Fix Keycloak custom flat mapper — it corrupts resource_access in service account tokens, forcing use of over-privileged admin/admin-cli credentials for role fetching. Fix: remove the custom mapper from blitz-internal realm so standard resource_access.realm-management.roles format applies, then revert keycloak_client.py to client_credentials grant with only view-users + query-users roles
- [ ] [TECH DEBT] Move KEYCLOAK_ADMIN_PASSWORD + KEYCLOAK_CLIENT_SECRET out of docker-compose.local.yml defaults into backend/.env (already done via env var substitution, but add explicit values to .env template/.dev-secrets.example)
- [ ] [POST-MVP] HashiCorp Vault for secret management — replace .env file secrets + DB AES-256 with Vault for rotation, audit trail, and zero-trust credential access
- [ ] Add user preferences for LLM thinking mode (on/off) and response style (concise/detailed/auto) — backend API + chat UI session controls + LiteLLM extra_body passthrough
- [ ] Add user profile and logout to UI with session expiration — profile menu, logout endpoint, auto-logout timer, configurable session timeout in settings

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 3 | Fix all tech debt from v1.2 audit | 2026-03-04 | be8f9c0 | [3-fix-all-tech-debt-from-v1-2-audit](./quick/3-fix-all-tech-debt-from-v1-2-audit/) |

### Blockers/Concerns

- WhatsApp Business API verification takes 1-4 weeks — start process early (not blocking v1.2)
- uv run subcommands time out on this machine — use `.venv/bin/` paths directly for CLI tools
- Alembic migration from host requires `.env` — apply via `docker exec psql` inside container

## Session Continuity

Last session: 2026-03-04
Stopped at: Completed quick-3 — v1.2 tech debt cleanup (5 items, 2 tasks, 0 regressions)
Resume file: .planning/phases/14-ecosystem-capabilities/14-05-SUMMARY.md
