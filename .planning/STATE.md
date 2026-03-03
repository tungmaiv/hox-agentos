---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Developer Experience
status: unknown
last_updated: "2026-03-03T14:15:20Z"
progress:
  total_phases: 3
  completed_phases: 2
  total_plans: 6
  completed_plans: 6
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-02 after v1.2 roadmap)

**Core value:** Every Blitz employee gets an intelligent, context-aware assistant that automates their daily work routines and lets them build custom automations without writing code — all within an enterprise-secure, on-premise environment where data never leaves the company.
**Current focus:** v1.2 Developer Experience — Phase 13 complete, Phase 14 next

## Current Position

Milestone: v1.2 Developer Experience
Phase: 13 of 14 (Local Auth) — COMPLETE (both plans done)
Status: Phase 13 Plan 02 COMPLETE — frontend local auth: Credentials provider + dual login page + admin Users tab
Last activity: 2026-03-03 — Phase 13-02 frontend local auth: NextAuth Credentials, redesigned /login, /admin/users CRUD

Progress: [███░░░░░░░░░] 23% — v1.2 Phase 13 complete, Phase 14 next

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

### Pending Todos

- [ ] Start WhatsApp Business API verification process (takes 1-4 weeks, needed for future live testing)
- [ ] Add CREDENTIAL_ENCRYPTION_KEY to production .env before Phase 3 OAuth flows
- [ ] [TECH DEBT] Fix Keycloak custom flat mapper — it corrupts resource_access in service account tokens, forcing use of over-privileged admin/admin-cli credentials for role fetching. Fix: remove the custom mapper from blitz-internal realm so standard resource_access.realm-management.roles format applies, then revert keycloak_client.py to client_credentials grant with only view-users + query-users roles
- [ ] [TECH DEBT] Move KEYCLOAK_ADMIN_PASSWORD + KEYCLOAK_CLIENT_SECRET out of docker-compose.local.yml defaults into backend/.env (already done via env var substitution, but add explicit values to .env template/.dev-secrets.example)
- [ ] [POST-MVP] HashiCorp Vault for secret management — replace .env file secrets + DB AES-256 with Vault for rotation, audit trail, and zero-trust credential access
- [ ] Add user preferences for LLM thinking mode (on/off) and response style (concise/detailed/auto) — backend API + chat UI session controls + LiteLLM extra_body passthrough

### Blockers/Concerns

- WhatsApp Business API verification takes 1-4 weeks — start process early (not blocking v1.2)
- uv run subcommands time out on this machine — use `.venv/bin/` paths directly for CLI tools
- Alembic migration from host requires `.env` — apply via `docker exec psql` inside container

## Session Continuity

Last session: 2026-03-03
Stopped at: Phase 13 Plan 02 COMPLETE — frontend local auth done (Credentials provider + redesigned /login + admin Users tab + 8 proxy routes; pnpm build 0 errors)
