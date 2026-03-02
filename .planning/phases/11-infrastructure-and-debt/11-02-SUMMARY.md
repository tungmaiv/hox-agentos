---
phase: 11-infrastructure-and-debt
plan: "02"
subsystem: infra/dead-code
tags: [cloudflare-tunnel, dead-code, tech-debt, sweep, documentation]
dependency_graph:
  requires: ["11-01"]
  provides: [docs/dev-context.md (tunnel section), dead-code markers]
  affects:
    - backend/agents/subagents/router.py (deleted)
    - backend/tests/agents/test_router.py (deleted)
    - backend/agents/master_agent.py (tech-debt annotation + TODO marker)
    - docs/dev-context.md (Cloudflare Tunnel section)
    - frontend/src/lib/api-client.ts (TODO marker)
tech_stack:
  added: []
  patterns: [TODO comment convention for uncertain dead code]
key_files:
  created: []
  modified:
    - docs/dev-context.md
    - backend/agents/master_agent.py
    - frontend/src/lib/api-client.ts
  deleted:
    - backend/agents/subagents/router.py
    - backend/tests/agents/test_router.py
decisions:
  - "router.py deletion confirmed safe — zero production callers of classify_intent verified before deletion"
  - "_route_after_master in plan refers to _pre_route in code (function was renamed); TODO(tech-debt) comment placed on _pre_route"
  - "update_agent_last_seen and serverFetch marked TODO: verify dead — no production callers but not confirmed dead (could be wired in future phases)"
  - "save_fact/save_episode not flagged — used in tests and designed for Celery worker wiring"
  - "clear_cache() not flagged — explicitly documented as test isolation utility in 11-01 SUMMARY"
metrics:
  duration_seconds: 265
  tasks_completed: 4
  files_created: 0
  files_modified: 3
  files_deleted: 2
  completed_date: "2026-03-02"
---

# Phase 11 Plan 02: Tunnel Documentation + Dead Code Removal Summary

**One-liner:** Cloudflare Tunnel documented at 172.16.155.118, classify_intent dead code deleted, _pre_route annotated as Agent-as-Tool tech debt, and codebase sweep marked 2 uncertain symbols with TODO: verify dead.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Document Cloudflare Tunnel in docs/dev-context.md | 6b9e84b | docs/dev-context.md |
| 2 | Delete classify_intent dead code (router.py + test_router.py) | 2a122ad | deleted 2 files |
| 3 | Annotate _pre_route as deferred tech debt | 5dd8533 | backend/agents/master_agent.py |
| 4 | Dead code sweep — backend Python, frontend TypeScript, infra/config | d469269 | master_agent.py, api-client.ts |

## What Was Built

**Task 1 — Cloudflare Tunnel documentation**

Added a new `## Cloudflare Tunnel (Webhook Routing)` section to `docs/dev-context.md`:
- Documents tunnel IP `172.16.155.118` running on an external machine
- Clarifies that no `cloudflared` container exists in docker-compose.yml
- States INFRA-01 (webhook exposure) and INFRA-02 (tunnel-as-service) are satisfied externally
- Lists all three channel webhook endpoints exposed through the tunnel
- Added Update Log entry dated 2026-03-02

**Task 2 — Dead code deletion**

`backend/agents/subagents/router.py` and `backend/tests/agents/test_router.py` deleted after confirming zero production callers:
- `grep classify_intent` across all backend Python (excluding the two files themselves) returned zero results
- 6 tests in test_router.py removed; test suite went from 606 to 600 passed (the 1 skipped was pre-existing)
- Full suite: 600 passed, 1 skipped, zero failures after deletion

**Task 3 — Tech debt annotation**

Added 8-line `TODO(tech-debt)` comment block above `_pre_route` in `master_agent.py`:
- Explains current keyword-map routing approach and its limitations
- Names the correct replacement: Agent-as-Tool pattern (LLM-native tool selection)
- Cites the specific blocker: "DO NOT remove this function until the Agent-as-Tool routing phase is complete"
- Points to Phase 11 CONTEXT.md -> Deferred Ideas for tracking

Note: The plan referenced `_route_after_master` but the current code uses `_pre_route` (renamed in an earlier refactor). The TODO comment was placed on `_pre_route` since that is the active keyword routing function.

**Task 4 — Dead code sweep**

Sweep covered backend Python, frontend TypeScript/TSX, and infra/config:

*Backend Python — findings:*
- `backend/agents/subagents/`: only calendar/email/project agents remain after router.py deletion; all actively wired
- `backend/memory/`: `save_fact`, `save_episode`, `mark_fact_superseded` all have callers (routes + tests)
- `backend/sandbox/`: `SandboxExecutor` used by `node_handlers.py` and `main.py` cleanup
- `backend/channels/gateway.py`: `_format_*` private helpers called internally by `format_for_channel`
- `backend/core/prompts.py` `clear_cache()`: documented test utility — not flagged (intentional design)
- `master_agent.py update_agent_last_seen`: no production callers → flagged `# TODO: verify dead`

*Frontend TypeScript — findings:*
- `use-mcp-tool`: consumed by `EmailSummaryCard.tsx` and `ProjectStatusWidget.tsx`
- `usePendingHitl`: consumed by `app/workflows/_pending-badge.tsx`
- `useAdminPermissions`: consumed by `permission-matrix.tsx` and `admin/permissions/page.tsx`
- `useSkills`: consumed by `chat-panel.tsx`
- `mapArraySnakeToCamel`: consumed by multiple hooks and admin pages
- `serverFetch` in `lib/api-client.ts`: no import callers anywhere → flagged `// TODO: verify dead`

*Infra/config — findings:*
- `LITELLM_MASTER_KEY`: consumed by `backend/core/config.py` as `litellm_master_key` field
- `TELEGRAM_BOT_TOKEN`: consumed by `infra/grafana/provisioning/alerting/contact_points.yml`
- No orphaned infra env vars found

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _route_after_master renamed to _pre_route**
- **Found during:** Task 3
- **Issue:** Plan Task 3 says "locate `_route_after_master` function definition" but the function was renamed to `_pre_route` in a prior refactor (Phase 6 slash command routing addition). The docstring in master_agent.py still references `_route_after_master` in the graph topology diagram.
- **Fix:** Placed the `TODO(tech-debt)` comment above `_pre_route` since that is the active keyword routing function. The module docstring topology diagram was left as-is (minor doc drift, not a functional issue).
- **Files modified:** `backend/agents/master_agent.py`
- **Commit:** 5dd8533

## Verification Results

- Full test suite after all 4 tasks: **600 passed, 1 skipped** (zero failures)
- `grep classify_intent` in backend Python: **zero results**
- `grep 172.16.155.118` in docs/dev-context.md: **2 matches** (section + update log)
- `grep TODO(tech-debt)` in master_agent.py: **1 match** at line 434
- TypeScript check (`pnpm exec tsc --noEmit`): **clean** (no errors)
- `TODO: verify dead` markers placed: **2** (update_agent_last_seen, serverFetch)

## Self-Check: PASSED
