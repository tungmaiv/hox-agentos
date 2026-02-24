# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-24)

**Core value:** Every Blitz employee gets an intelligent, context-aware assistant that automates daily work routines and lets them build custom automations without writing code -- all within an enterprise-secure, on-premise environment.
**Current focus:** Phase 1: Identity and Infrastructure Skeleton

## Current Position

Phase: 1 of 8 (Identity and Infrastructure Skeleton)
Plan: 1 of 4 in current phase
Status: In progress
Last activity: 2026-02-24 -- Completed 01-01-PLAN.md (Infrastructure and Project Scaffold)

Progress: [█░░░░░░░░░] 5% (1/20 plans estimated)

## Performance Metrics

**Velocity:**
- Total plans completed: 1
- Average duration: 7 min
- Total execution time: 0.12 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 1 | 7 min | 7 min |

**Recent Trend:**
- Last 5 plans: 7 min
- Trend: Baseline established

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Split Phase 2 vertically into "Agent Core" (Phase 2) and "Sub-Agents + Memory + Integrations" (Phase 3) to create testable delivery boundaries
- [Roadmap]: Phases 4 (Canvas) and 5 (Channels) can run in parallel -- no mutual dependencies
- [Research]: MCP transport should use Streamable HTTP (not SSE) per spec update 2025-03-26; SDK supports both
- [Research]: Start WhatsApp Business API verification process during Phase 1 (takes 1-4 weeks)
- [Research]: Use Next.js 15.5 (not 16) until CopilotKit confirms 16.x compatibility
- [01-01]: next-auth@5 tag does not exist on npm; use next-auth@beta (5.0.0-beta.30) for Auth.js v5 API
- [01-01]: uv run subcommands time out on this machine; use direct .venv/bin/ binary paths for alembic and pytest
- [01-01]: alembic.ini must use relative script_location = alembic (not absolute path) for portability
- [01-01]: pythonpath = ["."] required in pytest config so core/ module is importable from tests/

### Pending Todos

None.

### Blockers/Concerns

- WhatsApp Business API verification takes 1-4 weeks -- start process early even though adapter is Phase 5
- A2UI is in Public Preview (v0.8) -- monitor for breaking changes before Phase 3
- CopilotKit + LangGraph HITL has known ZodError -- use graph interrupt nodes instead (affects Phase 4)
- uv run subcommands time out on this machine; use .venv/bin/ paths directly for CLI tools

## Session Continuity

Last session: 2026-02-24T14:01:46Z
Stopped at: Completed 01-01-PLAN.md — infrastructure scaffold, 3 tasks, 13 tests passing
Resume file: None
