# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — MVP

**Shipped:** 2026-02-26
**Phases:** 5 | **Plans:** 17

### What Was Built
- Docker Compose 6-service stack with Keycloak SSO and 3-gate security
- LangGraph master agent with AG-UI streaming, AES-256 credential vault, per-user memory
- 3-tier memory: short-term turns, medium-term episode summaries, long-term pgvector facts
- Email/Calendar/Project sub-agents with A2UI generative UI cards
- MCP HTTP+SSE framework with hot-registration

### What Worked
- GSD phase-based planning kept scope tight — 17 plans in 2 days
- Inserted phases (2.1, 3.1) handled gaps without disrupting flow
- pgvector in PostgreSQL eliminated operational complexity of separate vector DB

### What Was Inefficient
- CopilotKit protocol discovery took multiple sessions (no documentation available)
- Keycloak self-signed cert and custom flat mapper caused hours of debugging
- `uv run` timeouts discovered late — should have established canonical commands earlier

### Patterns Established
- `.venv/bin/` direct invocation instead of `uv run` for all CLI tools
- Contextvar fallback pattern for LangGraph state fields
- CLAUDE.md gotchas section for hard-won discoveries

### Key Lessons
1. Always read the actual HTTP traffic (not documentation) when integrating undocumented protocols
2. Self-signed certs need explicit handling everywhere — add to gotchas immediately on discovery
3. Inserted phases (decimal numbering) are better than cramming fixes into existing plans

---

## Milestone: v1.1 — Enterprise Platform

**Shipped:** 2026-03-02
**Phases:** 9 | **Plans:** 33

### What Was Built
- React Flow canvas → LangGraph compiler with HITL approval gates
- Multi-channel presence (Telegram live, WhatsApp/Teams code-complete)
- Database-backed extensibility registries with admin dashboard
- Docker sandbox for untrusted code execution
- Grafana + Loki + Alloy observability stack

### What Worked
- Parallel phase execution (where dependencies allowed) compressed timeline
- ChannelAdapter protocol made adding channels incremental
- Skill import pipeline with AST safety caught issues early

### What Was Inefficient
- Observability stack (Phase 8) took 199 minutes — largest single plan; should have been split
- WhatsApp/Teams channels code-complete but untestable without live credentials
- Tech debt accumulated across phases required 2 cleanup phases (9, 10)

### Patterns Established
- `just` recipes for all common operations (backend, frontend, stop, kill, dev)
- Kill recipes need bash shebang to prevent pkill self-targeting
- Docker env vars: `docker compose up -d` (not `restart`) to pick up changes

### Key Lessons
1. Split plans that touch infrastructure (Grafana, Docker configs) from application code
2. Start credential acquisition processes early — WhatsApp/Teams blocked by external dependencies
3. Tech debt phases after major milestones are worth the investment

---

## Milestone: v1.2 — Developer Experience

**Shipped:** 2026-03-04
**Phases:** 4 | **Plans:** 11

### What Was Built
- Unified admin desk at /admin with AI-assisted artifact creation wizard
- Local user/group management with dual-issuer JWT dispatch
- system.capabilities tool with CapabilitiesCard A2UI
- OpenAPI-to-MCP bridge with 3-step admin wizard
- External skill repository ecosystem with browse, import, and agentskills.io export
- PromptLoader for externalized LLM prompts

### What Worked
- Milestone audit before completion caught 6 tech debt items — quick-3 fixed them before shipping
- Phase 14 split into 5 plans kept each unit testable and reviewable
- check-name endpoints declared BEFORE /{id} routes — FastAPI routing collision pattern well-understood now
- fill_form co-agent tool pattern enables AI-assisted forms without complex UI state

### What Was Inefficient
- Phase 14 initially had 4 plans but needed a 5th (14-05) for openapi_proxy dispatch wiring
- SUMMARY.md files lack `one_liner` frontmatter — milestone tooling couldn't auto-extract accomplishments
- Some admin UI flows (wizard, skill store) need live browser testing that automated tests can't cover

### Patterns Established
- Dual-issuer JWT dispatch by `iss` claim — extensible to future auth providers
- handler_type enum on tool_definitions for dispatch routing (backend, mcp_server, openapi_proxy)
- SecurityScanner quarantine pattern for imported artifacts
- Admin proxy binary fix: Content-Type branching for arrayBuffer vs text responses

### Key Lessons
1. Always add a `one_liner` field to SUMMARY.md frontmatter for milestone tooling
2. FastAPI route ordering is critical — literal paths before parameterized paths
3. Milestone audits before completion are high-value — catching tech debt before shipping keeps it visible
4. bcrypt 5.x breaks passlib 1.7.4 — use direct bcrypt instead of passlib for new code

### Cost Observations
- Model mix: ~70% opus (planning + execution), ~30% sonnet/haiku (quick tasks)
- Sessions: ~8 across phases 11-14
- Notable: Phase 14 was the most plan-dense (5 plans) but executed smoothly due to clear dependencies

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 5 | 17 | Established GSD workflow, gotchas section, canonical commands |
| v1.1 | 9 | 33 | Added tech debt phases, justfile recipes, parallel execution |
| v1.2 | 4 | 11 | Added milestone audit, prompt externalization, dual auth |

### Cumulative Quality

| Milestone | Tests | LOC | New Migrations |
|-----------|-------|-----|----------------|
| v1.0 | 180 | ~58K | 001–009 |
| v1.1 | 586 | ~72K | 010–017 |
| v1.2 | 719 | ~83K | 018–019 |

### Top Lessons (Verified Across Milestones)

1. **Canonical commands first** — establish and document exact CLI invocations before coding; wrong commands waste hours (verified v1.0, v1.1, v1.2)
2. **Inserted phases are cheap** — decimal phases (2.1, 3.1, 4.1, 5.1) handle gaps cleanly without disrupting the roadmap (verified v1.0, v1.1)
3. **Tech debt phases pay for themselves** — dedicated cleanup phases after major milestones prevent accumulation (verified v1.1, v1.2)
4. **FastAPI route ordering matters** — literal paths must precede parameterized paths; this pattern recurs every time new admin routes are added (verified v1.1, v1.2)
5. **External credential dependencies block testing** — start acquisition processes early; code-complete without live testing is a recurring pattern (verified v1.1 WhatsApp/Teams, v1.2 audit)
