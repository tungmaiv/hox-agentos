# Roadmap: Blitz AgentOS

## Milestones

- ✅ **v1.0 MVP** — Phases 1–3.1 (shipped 2026-02-26)
- 🚧 **v1.1** — Phases 4–8 (planned)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–3.1) — SHIPPED 2026-02-26</summary>

- [x] **Phase 1: Identity and Infrastructure Skeleton** — 4/4 plans (completed 2026-02-24)
- [x] **Phase 2: Agent Core and Conversational Chat** — 5/5 plans (completed 2026-02-25)
- [x] **Phase 2.1: Tech Debt Cleanup** (INSERTED) — 1/1 plan (completed 2026-02-26)
- [x] **Phase 3: Sub-Agents, Memory, and Integrations** — 6/6 plans (completed 2026-02-26)
- [x] **Phase 3.1: Memory Read Path & MCP Hot-Registration** (INSERTED) — 1/1 plan (completed 2026-02-26)

Full phase details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

### 🚧 v1.1 (Planned)

- [x] **Phase 4: Canvas and Workflows** — React Flow visual builder, canvas-to-StateGraph compiler, workflow templates, HITL approval, cron/webhook triggers (completed 2026-02-27)
- [x] **Phase 4.1: Phase 4 Polish** (INSERTED) — HITL canvas node amber ring fix, Next.js webhook proxy (completed 2026-02-27)
- [x] **Phase 5: Scheduler and Channels** — Web chat enhancement, Telegram/WhatsApp/Teams adapters, channel identity resolution, ChannelAdapter protocol (completed 2026-02-28)
- [x] **Phase 5.1: Workflow Execution Wiring** (INSERTED) — Fix workflow→channel delivery, wire real agent_node dispatch, Celery worker role passthrough (completed 2026-02-28)
- [x] **Phase 6: Extensibility Registries** — Database-backed registries for agents/tools/skills/MCP servers, CRUD APIs, per-artifact permissions, skill runtime with /command support, admin dashboard UI, built-in skill seeds (completed 2026-03-01)
- [x] **Phase 7: Hardening and Sandboxing** — Docker sandbox execution, security audit, RLS policies, credential scanning, penetration testing (completed 2026-03-01)
- [x] **Phase 8: Observability** — Grafana dashboards, Loki log aggregation, LiteLLM cost tracking (completed 2026-03-01)
- [x] **Phase 9: Tech Debt Code Fixes** — Cache invalidation on tool status/version changes, LLM metric instrumentation, docstring correctness
- [x] **Phase 10: Optional Tech Debt Closure** — ChannelAdapter runtime enforcement, channel LangGraph continuity, delivery_router unification, UAT test 12, Grafana alert live test, Phase 4.1 VERIFICATION.md (completed 2026-03-01)

## Phase Details

### Phase 4: Canvas and Workflows
**Goal**: Users can visually build multi-step automations on a drag-and-drop canvas that compile to executable agent workflows with human approval gates
**Depends on**: Phase 3
**Requirements**: WKFL-01, WKFL-02, WKFL-03, WKFL-04, WKFL-05, WKFL-06, WKFL-07, WKFL-08, WKFL-09
**Success Criteria** (what must be TRUE):
  1. User can drag nodes onto a React Flow canvas, connect them with edges, and save the workflow with schema_version in definition_json
  2. A saved canvas workflow compiles to a LangGraph StateGraph and executes end-to-end (nodes fire in sequence, data passes between them)
  3. User can create and run a Morning Digest workflow (Email Fetch → Summarize → Send to Channel) from a pre-built template
  4. User can create and run an Alert workflow (Trigger keyword → Create Task → Notify) from a pre-built template
  5. Workflow pauses at HITL approval nodes and waits for human input via A2UI before continuing
**Plans**: TBD

Plans:
- [ ] 04-01: React Flow canvas UI with node palette and workflow CRUD
- [ ] 04-02: Canvas-to-StateGraph compiler and execution engine
- [ ] 04-03: Workflow triggers (cron scheduling and webhook/events)
- [ ] 04-04: HITL approval nodes and A2UI integration
- [ ] 04-05: Pre-built workflow templates (Morning Digest, Alert)

### Phase 4.1: Phase 4 Polish
**Goal**: Close two non-blocking tech debt items from the Phase 4 milestone audit before continuing to Phase 5
**Depends on**: Phase 4
**Gap Closure**: Closes tech debt items from v1.1-MILESTONE-AUDIT.md
**Success Criteria** (what must be TRUE):
  1. HITL approval node on canvas turns amber (`awaiting_approval` ring activates) when workflow pauses at an HITL node — `hitl_paused` SSE event includes `node_id` from `state_snapshot.next[0]`
  2. Next.js proxy route exists at `/api/webhooks/[webhook_id]` matching the pattern of all other workflow proxy routes

Plans:
- [x] 04.1-01: HITL canvas node amber ring fix + Next.js webhook proxy

### Phase 5: Scheduler and Channels
**Goal**: Users can interact with the agent from Telegram, WhatsApp, and MS Teams in addition to web chat, and workflows run on cron schedules as the owning user's context
**Depends on**: Phase 3 (can run in parallel with Phase 4)
**Requirements**: CHAN-01, CHAN-02, CHAN-03, CHAN-04, CHAN-05, CHAN-06
**Success Criteria** (what must be TRUE):
  1. User can send a message to the Blitz Telegram bot and receive agent responses with full tool access
  2. User can interact with the agent via WhatsApp Business and receive the same capabilities as web chat
  3. User can interact with the agent via MS Teams with the same capabilities as web chat
  4. External platform user IDs (Telegram, WhatsApp, Teams) are mapped to Blitz user IDs via channel_accounts table — unlinked users receive a pairing prompt
  5. New channel adapters can be added by implementing the ChannelAdapter protocol without modifying agent, tool, or memory code
**Plans**: 6 plans

Plans:
- [x] 05-01-PLAN.md — Core: DB models, InternalMessage, ChannelGateway, pairing, backend routes
- [x] 05-02-PLAN.md — Telegram sidecar (FastAPI service + Docker)
- [x] 05-03-PLAN.md — WhatsApp Cloud API sidecar (FastAPI service + Docker)
- [x] 05-04-PLAN.md — MS Teams Bot Framework sidecar (FastAPI service + Docker)
- [x] 05-05-PLAN.md — Integration wiring: agent invocation, delivery router, frontend settings
- [x] 05-06-PLAN.md — Gap closure: formal ChannelAdapter(Protocol) class (CHAN-05)

### Phase 5.1: Workflow Execution Wiring
**Goal**: Close integration gaps from v1.1 milestone audit — workflow channel delivery, real agent_node dispatch, and Celery worker role passthrough so that canvas workflows with channel output nodes deliver messages to linked channels
**Depends on**: Phase 5
**Gap Closure**: Closes gaps from v1.1-MILESTONE-AUDIT.md
**Requirements**: WKFL-03 (partial→satisfied), WKFL-04 (partial→satisfied)
**Success Criteria** (what must be TRUE):
  1. A workflow with a `channel_output_node` targeting Telegram delivers the message to the workflow owner's linked Telegram chat — `external_chat_id` is resolved from `channel_accounts` table using `owner_user_id` + channel type
  2. A workflow `agent_node` invokes the real sub-agent (email, calendar, project) and returns actual LLM-generated output instead of stub text
  3. Celery workflow workers use the workflow owner's actual Keycloak roles instead of hardcoded `['employee']`

**Plans:** 1 plan

Plans:
- [x] 05.1-01-PLAN.md — Channel output delivery + agent_node real dispatch + Keycloak role passthrough + tests

### Phase 6: Extensibility Registries
**Goal**: Admins and developers can manage the platform's agents, tools, skills, and MCP servers as runtime artifacts through database-backed registries with granular permissions, with a skill runtime supporting /command invocation, a secure skill import pipeline, and a frontend admin dashboard
**Depends on**: Phases 4 and 5
**Requirements**: EXTD-01, EXTD-02, EXTD-03, EXTD-04, EXTD-05, EXTD-06
**Success Criteria** (what must be TRUE):
  1. Every agent, tool, skill, and MCP server has a database registry entry with name, description, version, status, and required permissions
  2. Admin can add, edit, disable, and re-enable any artifact via API and admin UI — disabled artifacts are unavailable to agents
  3. Developer can register a new tool or MCP server and it becomes available to authorized users without restarting the backend
  4. Permissions can be assigned per artifact per role, with per-user overrides and staged apply model
  5. Removing an artifact from the registry prevents all future invocations; existing running workflows complete gracefully
  6. Admin dashboard at /admin shows all artifacts with table/card views, permission matrix, and MCP connectivity indicators
**Plans**: 8 plans

Plans:
- [x] 06-01-PLAN.md — ORM models (6 tables + MCP evolution), Alembic migration 014 with seed data + tool_acl migration, Pydantic schemas
- [x] 06-02-PLAN.md — RBAC migration to DB-backed role_permissions with cache, artifact permissions with staged model
- [x] 06-03-PLAN.md — Admin CRUD APIs with multi-version, bulk status, staged permissions, per-user overrides, graceful removal
- [x] 06-04-PLAN.md — Runtime integration: tool registry DB, agent graph DB, MCP evolution, startup seeding, last_seen_at tracking
- [x] 06-05-PLAN.md — Skill system: executor with AG-UI streaming, AST-based safe evaluator, validator, import pipeline, security scanner
- [x] 06-06-PLAN.md — User skill/tool APIs, slash command dispatch, frontend skill menu, integration wiring
- [x] 06-07-PLAN.md — Frontend admin dashboard: tabbed UI, table/card views, permission matrix, MCP dots
- [x] 06-08-PLAN.md — Gap closure: seed built-in skills (migration 015), fix Pending Review filter predicate

### Phase 7: Hardening and Sandboxing
**Goal**: Untrusted code executes safely in sandboxed containers, and the full security perimeter is verified through automated testing and policy enforcement
**Depends on**: Phase 6
**Requirements**: SBOX-01, SBOX-02, SBOX-03
**Success Criteria** (what must be TRUE):
  1. Untrusted code executes in a Docker container with enforced CPU, memory, and network limits
  2. Sandbox containers have zero access to the host filesystem
  3. Sandbox containers are destroyed after execution or timeout with no resource leaks
  4. Cross-user memory isolation verified by automated penetration tests
  5. PostgreSQL Row Level Security policies enforce user_id isolation as defense-in-depth
**Plans**: 4 plans (2 gap closure)

Plans:
- [ ] 07-01-PLAN.md — Docker sandbox executor: SandboxExecutor TDD, resource limits (CPU=0.5, RAM=256MB, no network), tool registry dispatch wiring
- [ ] 07-02-PLAN.md — Security hardening: RLS migration 016 on 6 tables, set_rls_user_id helper, cross-user isolation pen tests, bandit dev dep
- [ ] 07-03-PLAN.md — Gap closure: fix lazy import defect in test_isolation.py (isolation test determinism)
- [ ] 07-04-PLAN.md — Gap closure: install trufflehog and run git history credential scan

### Phase 8: Observability
**Goal**: Operations team can monitor system health, agent performance, LLM costs, and troubleshoot issues through centralized dashboards and log aggregation
**Depends on**: Phase 7
**Requirements**: OBSV-01, OBSV-02, OBSV-03
**Success Criteria** (what must be TRUE):
  1. Grafana dashboards show real-time system health and agent performance
  2. All service logs aggregated in Loki via Alloy, searchable by service/user/tool/time
  3. LiteLLM cost tracking dashboard shows spend by model alias and user
**Plans**: 3 plans

Plans:
- [x] 08-01-PLAN.md — Docker Compose infra stack (prometheus, grafana, loki, alloy, cadvisor) + all config files
- [ ] 08-02-PLAN.md — Backend Prometheus instrumentation (metrics.py, /metrics endpoint, LiteLLM callback)
- [ ] 08-03-PLAN.md — Grafana dashboards (Ops + Costs), alerting provisioning, Keycloak SSO verification

### Phase 9: Tech Debt Code Fixes
**Goal:** Close 3 actionable medium/low-severity tech debt items identified in the v1.1 audit — tool status cache invalidation, LLM metric instrumentation, and docstring correctness
**Depends on:** Phase 8
**Gap Closure:** Closes tech debt from v1.1-MILESTONE-AUDIT.md
**Requirements:** EXTD-03 (partial→fully-wired), EXTD-05 (partial→fully-wired), OBSV-01 (partial→fully-wired)
**Success Criteria** (what must be TRUE):
  1. Calling `patch_tool_status()` or `activate_tool_version()` immediately invalidates the tool cache — disabled tools are unavailable within the same request, not after 60s TTL expiry
  2. Each `get_llm()` call increments `blitz_llm_calls_total` — the Prometheus metric reads > 0 after agent conversations in a live environment
  3. `list_templates` endpoint docstring accurately describes its auth requirement (JWT required)
**Plans:** 2/2 plans complete

Plans:
- [x] 09-01-PLAN.md — Cache invalidation (patch_tool_status + activate_tool_version), list_templates docstring fix, regression tests
- [x] 09-02-PLAN.md — LLM metric wiring: blitz_llm_calls_total status label + _LLMMetricsCallback in get_llm(), update + new tests

### Phase 10: Optional Tech Debt Closure
**Goal:** Close 6 low-severity tech debt items — ChannelAdapter runtime enforcement, channel conversation continuity, delivery routing unification, UAT test coverage, Grafana alert live verification, and Phase 4.1 documentation gap
**Depends on:** Phase 9
**Gap Closure:** Closes tech debt from v1.1-MILESTONE-AUDIT.md
**Requirements:** CHAN-05 (isinstance enforcement), CHAN-02 (channel continuity), EXTD-06 (UAT test 12)
**Success Criteria** (what must be TRUE):
  1. `ChannelGateway` enforces `isinstance(adapter, ChannelAdapter)` at adapter registration time — non-conforming adapters raise `TypeError` at startup
  2. Multi-turn channel conversations maintain context across messages — LangGraph checkpointer is shared across `_invoke_agent()` calls for the same `channel_session_id`
  3. Channel invocations flow through `delivery_router` like web chat invocations — no special-cased bypass in master agent
  4. UAT test 12 (Admin Create Skill via API) is implemented and passes in the full test suite
  5. Grafana → Telegram spend alert is live-tested end-to-end with a manual threshold breach
  6. `04.1-VERIFICATION.md` exists documenting both Phase 4.1 success criteria
**Plans:** 2/2 plans complete

Plans:
- [ ] 10-01-PLAN.md — ChannelAdapter isinstance enforcement + channel LangGraph continuity + delivery_router unification
- [ ] 10-02-PLAN.md — UAT test 12 + Grafana alert live test + Phase 4.1 VERIFICATION.md

## Progress

**Execution Order:** 1 → 2 → 2.1 → 3 → 3.1 → 4 → 4.1 → 5 → 5.1 → 6 → 7 → 8 → 9 → 10

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1. Identity & Skeleton | v1.0 | 4/4 | ✅ Complete | 2026-02-24 |
| 2. Agent Core & Chat | v1.0 | 5/5 | ✅ Complete | 2026-02-25 |
| 2.1. Tech Debt Cleanup | v1.0 | 1/1 | ✅ Complete | 2026-02-26 |
| 3. Sub-Agents & Memory | v1.0 | 6/6 | ✅ Complete | 2026-02-26 |
| 3.1. Memory Read + MCP Hot-Reg | v1.0 | 1/1 | ✅ Complete | 2026-02-26 |
| 4. Canvas & Workflows | v1.1 | 5/5 | ✅ Complete | 2026-02-27 |
| 4.1. Phase 4 Polish (INSERTED) | v1.1 | 1/1 | ✅ Complete | 2026-02-27 |
| 5. Scheduler & Channels | v1.1 | 6/6 | ✅ Complete | 2026-02-28 |
| 5.1. Workflow Execution Wiring (INSERTED) | v1.1 | 1/1 | ✅ Complete | 2026-02-28 |
| 6. Extensibility Registries | v1.1 | 8/8 | ✅ Complete | 2026-03-01 |
| 7. Hardening & Sandboxing | v1.1 | 4/4 | ✅ Complete | 2026-03-01 |
| 8. Observability | v1.1 | 4/4 | ✅ Complete | 2026-03-01 |
| 9. Tech Debt Code Fixes | v1.1 | Complete    | 2026-03-01 | — |
| 10. Optional Tech Debt Closure | 2/2 | Complete   | 2026-03-01 | — |
