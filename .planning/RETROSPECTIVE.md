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

## Milestone: v1.3 — Production Readiness & Skill Platform

**Shipped:** 2026-03-11
**Phases:** 9 (15–23) | **Plans:** 34 | **Tasks:** ~49
**Timeline:** 2026-03-05 → 2026-03-10 (6 days)
**Test suite:** 860 passed, 1 skipped | **LOC:** 80,620 Python + 18,959 TypeScript

### What Was Built
- Production session hardening: Next.js middleware (jose), HttpOnly cookies, silent refresh, CVE-2025-29927 mitigation
- Navigation rail + profile page with LLM thinking mode/response style preferences injected into agent prompt
- Embedding sidecar service (bge-m3 extracted from uvicorn, HTTP-first path, warm model, no cold-start)
- Keycloak as optional runtime config: local-auth-first boot, admin Identity tab, JWKS hot-reload without restart
- agentskills.io spec compliance: 7 metadata columns (migration 022), name validation, SKILL.md/ZIP import+export
- Skill catalog: PostgreSQL tsvector FTS with Vietnamese-compatible `simple` language, category/author filters, usage_count
- External skill registry browse with paginated index + one-click import through SecurityScanner quarantine
- SecurityScanner enhanced with dependency_risk + data_flow_risk factors + hard veto for undeclared imports
- allowed-tools enforcement pre-gate in SkillExecutor + SHA-256 daily update checker via Celery
- Promoted skills curated section + user-facing ZIP export + user-to-user sharing via artifact_permissions
- Builder generates procedure_json / instruction_markdown / handler_code stubs via single LLM shot
- pgvector similarity search over external skill repo index (HNSW cosine) + Fork capability
- SecurityScanner gate on all builder saves; SecurityReportCard A2UI + admin approval flow

### What Worked
- **Two parallel tracks** (Foundations 15–18, Skill Platform 19–23) enabled clear scoping — track completion felt like natural milestones
- **GSD's UAT-driven verification loop** caught 4 Phase 15 gaps and 3 Phase 20 gaps before the phase closed — each gap closure plan was precise and quick
- **Phase 19 done-without-PLAN.md pattern** — executor completed the work directly in one session; UAT proved it; no formal plans needed. Signals the executor is getting efficient at single-plan phases
- **SecurityScanner as a central trust gate** worked cleanly — same class used in 3 flows (ZIP import, registry import, builder-save); Phase 21 enhancements automatically applied everywhere
- **Migration chain discipline** — linear chain 020→027, no branching, single head throughout 9-phase milestone
- **Re-verification pattern** — Phases 15 and 20 had `previous_status: gaps_found` then confirmed `status: passed` after gap closure; this gave confidence before marking complete

### What Was Inefficient
- **Phase 19 process debt** — no PLAN.md, no VERIFICATION.md, REQUIREMENTS.md traceability not updated; required manual audit cleanup at milestone completion. Cost: ~30min of audit work.
- **Builder metadata gap discovered late** (at audit) — `allowed_tools`/`category`/`tags` not in `fill_form` mapping; should have been caught during Phase 23 planning or execution. Will carry to v1.4.
- **Phase 17 had 7 plans** — the most of any phase; PERF-01 through PERF-13 could have been batched into 4-5 plans without losing clarity
- **ROADMAP.md Phase Details section** — became stale during execution (plans marked `[ ] TBD` in the roadmap while summaries existed); roadmap wasn't kept in sync during execution

### Patterns Established
- **Skill ecosystem V-shape**: standards → catalog → security → sharing → builder; each phase depended on the previous. This dependency chain should be documented at the start of a skill ecosystem milestone
- **Admin UI + backend + frontend = 3 plans** became a reliable heuristic for feature phases with all three layers
- **SecurityScanner as central trust primitive** — adding new skill acquisition paths should always go through the scanner; this is now a project convention

### Key Lessons
1. **Always create VERIFICATION.md** — Phase 19 skipped it; the audit had to reconstruct evidence from UAT.md. 15 minutes of verification work saves 30 minutes of audit cleanup.
2. **Builder form fields need explicit mapping** — the `fill_form` tool mapping is the connection between LLM conversation and DB writes; it requires explicit field-by-field wiring that is easy to miss.
3. **Track 1 (foundations) before Track 2 (features)** — Phase 15 session hardening must precede Phase 16+ navigation; deploying the nav rail before middleware would have left auth holes. The dependency was correct.
4. **tsvector `simple` language is the right choice for multilingual** — confirmed: `english` config ignores Vietnamese tokens; `simple` passes them through. Document this decision clearly for any future FTS feature.
5. **Keycloak-optional boot pattern** — `platform_config` DB table with config resolution (DB → env → not configured) is clean and generalizable to other optional integrations.

### Cost Observations
- Model mix: sonnet throughout (balanced profile)
- Sessions: ~9 (one per phase; some phases required re-verification session)
- Notable: Phase 17 (7 plans) had the highest per-phase cost; splitting PERF requirements across fewer plans would reduce orchestration overhead

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 5 | 17 | Established GSD workflow, gotchas section, canonical commands |
| v1.1 | 9 | 33 | Added tech debt phases, justfile recipes, parallel execution |
| v1.2 | 4 | 11 | Added milestone audit, prompt externalization, dual auth |
| v1.3 | 9 | 34 | Two parallel tracks, SecurityScanner as central primitive, UAT-driven gap closure |

### Cumulative Quality

| Milestone | Tests | LOC | New Migrations |
|-----------|-------|-----|----------------|
| v1.0 | 180 | ~58K | 001–009 |
| v1.1 | 586 | ~72K | 010–017 |
| v1.2 | 719 | ~83K | 018–019 (021) |
| v1.3 | 860 | ~100K | 020–027 |

### Top Lessons (Verified Across Milestones)

1. **Canonical commands first** — establish and document exact CLI invocations before coding; wrong commands waste hours (verified v1.0, v1.1, v1.2)
2. **Inserted phases are cheap** — decimal phases (2.1, 3.1, 4.1, 5.1) handle gaps cleanly without disrupting the roadmap (verified v1.0, v1.1)
3. **Tech debt phases pay for themselves** — dedicated cleanup phases after major milestones prevent accumulation (verified v1.1, v1.2)
4. **FastAPI route ordering matters** — literal paths must precede parameterized paths; this pattern recurs every time new admin routes are added (verified v1.1, v1.2)
5. **External credential dependencies block testing** — start acquisition processes early; code-complete without live testing is a recurring pattern (verified v1.1 WhatsApp/Teams, v1.2 audit)
