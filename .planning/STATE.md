# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-02 after v1.2 roadmap)

**Core value:** Every Blitz employee gets an intelligent, context-aware assistant that automates their daily work routines and lets them build custom automations without writing code — all within an enterprise-secure, on-premise environment where data never leaves the company.
**Current focus:** v1.2 Developer Experience — Phase 11 in progress

## Current Position

Milestone: v1.2 Developer Experience
Phase: 11 of 14 (Infrastructure and Debt) — In progress (1/3 plans complete)
Plan: 11-01 complete — ready for 11-02
Status: Executing Phase 11
Last activity: 2026-03-02 — 11-01 Prompt Externalization complete (4 commits, 4 min)

Progress: [█░░░░░░░░░░░] 4% — v1.2 Phase 11 started

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

### Pending Todos

- [ ] Start WhatsApp Business API verification process (takes 1-4 weeks, needed for future live testing)
- [ ] Add CREDENTIAL_ENCRYPTION_KEY to production .env before Phase 3 OAuth flows

### Blockers/Concerns

- WhatsApp Business API verification takes 1-4 weeks — start process early (not blocking v1.2)
- uv run subcommands time out on this machine — use `.venv/bin/` paths directly for CLI tools
- Alembic migration from host requires `.env` — apply via `docker exec psql` inside container

## Session Continuity

Last session: 2026-03-02
Stopped at: Completed 11-01-PLAN.md — Prompt Externalization done. Next: 11-02 (Tunnel + AG-UI serialization)
