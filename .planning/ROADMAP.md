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
- [ ] **Phase 5.1: Workflow Execution Wiring** (INSERTED) — Fix workflow→channel delivery, wire real agent_node dispatch, Celery worker role passthrough
- [ ] **Phase 6: Extensibility Registries** — Database-backed registries for agents/tools/skills/MCP servers, CRUD APIs, per-artifact permissions
- [ ] **Phase 7: Hardening and Sandboxing** — Docker sandbox execution, security audit, RLS policies, credential scanning, penetration testing
- [ ] **Phase 8: Observability** — Grafana dashboards, Loki log aggregation, LiteLLM cost tracking

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

Plans:
- [ ] 05.1-01: Fix channel_output_node delivery + agent_node real dispatch + worker roles

### Phase 6: Extensibility Registries
**Goal**: Admins and developers can manage the platform's agents, tools, skills, and MCP servers as runtime artifacts through database-backed registries with granular permissions
**Depends on**: Phases 4 and 5
**Requirements**: EXTD-01, EXTD-02, EXTD-03, EXTD-04, EXTD-05, EXTD-06
**Success Criteria** (what must be TRUE):
  1. Every agent, tool, skill, and MCP server has a database registry entry with name, description, version, status, and required permissions
  2. Admin can add, edit, disable, and re-enable any artifact via API — disabled artifacts are unavailable to agents
  3. Developer can register a new tool or MCP server and it becomes available to authorized users without restarting the backend
  4. Permissions can be assigned per artifact per role
  5. Removing an artifact from the registry prevents all future invocations; existing running workflows complete gracefully
**Plans**: TBD

Plans:
- [ ] 06-01: Database models and CRUD APIs for artifact registries
- [ ] 06-02: Tool registry integration with runtime dispatch
- [ ] 06-03: Permission assignment and enforcement per artifact per role

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
**Plans**: TBD

Plans:
- [ ] 07-01: Docker sandbox executor with resource limits and cleanup
- [ ] 07-02: Security hardening (RLS, credential scanning, pen tests)

### Phase 8: Observability
**Goal**: Operations team can monitor system health, agent performance, LLM costs, and troubleshoot issues through centralized dashboards and log aggregation
**Depends on**: Phase 7
**Requirements**: OBSV-01, OBSV-02, OBSV-03
**Success Criteria** (what must be TRUE):
  1. Grafana dashboards show real-time system health and agent performance
  2. All service logs aggregated in Loki via Alloy, searchable by service/user/tool/time
  3. LiteLLM cost tracking dashboard shows spend by model alias and user
**Plans**: TBD

Plans:
- [ ] 08-01: Grafana and Loki setup with Alloy log collection
- [ ] 08-02: Dashboards for system health, agent performance, and LLM costs

## Progress

**Execution Order:** 1 → 2 → 2.1 → 3 → 3.1 → 4 → 4.1 → 5 → 5.1 → 6 → 7 → 8

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
| 5.1. Workflow Execution Wiring (INSERTED) | v1.1 | 0/1 | ○ Not started | — |
| 6. Extensibility Registries | v1.1 | 0/3 | ○ Not started | — |
| 7. Hardening & Sandboxing | v1.1 | 0/2 | ○ Not started | — |
| 8. Observability | v1.1 | 0/2 | ○ Not started | — |
