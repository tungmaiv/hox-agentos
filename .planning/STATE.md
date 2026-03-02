# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-02 after v1.2 roadmap)

**Core value:** Every Blitz employee gets an intelligent, context-aware assistant that automates their daily work routines and lets them build custom automations without writing code — all within an enterprise-secure, on-premise environment where data never leaves the company.
**Current focus:** v1.2 Developer Experience — Phase 11 in progress

## Current Position

Milestone: v1.2 Developer Experience
Phase: 11 of 14 (Infrastructure and Debt) — COMPLETE (all 3 plans + live E2E verified)
Status: Phase 11 complete — ready for Phase 12
Last activity: 2026-03-03 — Telegram E2E verified live (message in → LLM → formatted reply out)

Progress: [███░░░░░░░░░] 21% — v1.2 Phase 11 complete, Phase 12 next

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
- [11-live]: TELEGRAM_GATEWAY_URL in backend/.env must be docker service name when backend runs in Docker — localhost:9001 resolves inside container (nothing), not to gateway sidecar

### Pending Todos

- [ ] Start WhatsApp Business API verification process (takes 1-4 weeks, needed for future live testing)
- [ ] Add CREDENTIAL_ENCRYPTION_KEY to production .env before Phase 3 OAuth flows

### Blockers/Concerns

- WhatsApp Business API verification takes 1-4 weeks — start process early (not blocking v1.2)
- uv run subcommands time out on this machine — use `.venv/bin/` paths directly for CLI tools
- Alembic migration from host requires `.env` — apply via `docker exec psql` inside container

## Session Continuity

Last session: 2026-03-03
Stopped at: Phase 11 fully complete — Cloudflare Tunnel live, Docker dev workflow operational, Telegram E2E verified. Next: Phase 12
