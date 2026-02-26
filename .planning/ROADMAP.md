# Roadmap: Blitz AgentOS

## Overview

Blitz AgentOS delivers an on-premise agentic operating system for ~100 Blitz employees in 8 phases. The build order follows strict dependency chains: security foundation first, then a working conversational agent, then domain-specific sub-agents with memory and integrations, then the visual workflow canvas and multi-channel presence (in parallel), then extensibility registries, hardening, and finally observability. The core value proposition -- "intelligent assistant that automates daily work" -- is validated by Phase 4 completion. Phases 4 and 5 can execute in parallel.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Identity and Infrastructure Skeleton** - Keycloak SSO, JWT/RBAC security, Docker Compose services, FastAPI/Next.js skeletons (completed 2026-02-24)
- [x] **Phase 2: Agent Core and Conversational Chat** - Master agent with LangGraph, AG-UI streaming chat, conversation memory, LiteLLM routing, credential store, custom instructions (completed 2026-02-25)
- [x] **Phase 2.1: Tech Debt Cleanup** (INSERTED) - Fix BACKEND_URL env inconsistency, user_instructions.updated_at onupdate, REQUIREMENTS.md traceability checkboxes, ROADMAP.md plan checkbox
- [ ] **Phase 3: Sub-Agents, Memory, and Integrations** - Email/Calendar/Project/Channel sub-agents, 3-tier memory with embeddings, MCP framework, A2UI generative UI
- [ ] **Phase 3.1: Memory Read Path & MCP Hot-Registration** (INSERTED) - Wire load_recent_episodes() into agent context (MEMO-02), add MCPToolRegistry.refresh() after runtime server registration (INTG-01), fix stale test
- [ ] **Phase 4: Canvas and Workflows** - React Flow visual builder, canvas-to-StateGraph compiler, workflow templates, HITL approval, cron/webhook triggers
- [ ] **Phase 5: Scheduler and Channels** - Web chat enhancement, Telegram/WhatsApp/Teams adapters, channel identity resolution, ChannelAdapter protocol
- [ ] **Phase 6: Extensibility Registries** - Database-backed registries for agents/tools/skills/MCP servers, CRUD APIs, per-artifact permissions
- [ ] **Phase 7: Hardening and Sandboxing** - Docker sandbox execution, security audit, RLS policies, credential scanning, penetration testing
- [ ] **Phase 8: Observability** - Grafana dashboards, Loki log aggregation, LiteLLM cost tracking

## Phase Details

### Phase 1: Identity and Infrastructure Skeleton
**Goal**: Every request to the platform is authenticated, authorized, and audit-logged; all infrastructure services are healthy and communicating
**Depends on**: Nothing (first phase)
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06
**Success Criteria** (what must be TRUE):
  1. User can log in via Keycloak SSO and receive a valid session in the browser
  2. Backend rejects requests with missing, expired, or invalid JWT tokens with 401
  3. User with "employee" role can access agent endpoints; user with "viewer" role cannot invoke tools (RBAC enforced)
  4. Every tool call attempt is logged with user_id, tool name, allowed/denied, and duration -- no credentials appear in logs
  5. All Docker Compose services (PostgreSQL, Redis, Keycloak, LiteLLM, backend, frontend) start and pass health checks
**Plans**: 4 plans

Plans:
- [x] 01-01-PLAN.md — Docker Compose stack, backend Python scaffold (core/config, core/logging, core/db), Next.js 15.5 frontend scaffold with next-auth v5
- [x] 01-02-PLAN.md — JWT validation Gate 1: UserContext TypedDict, security/jwt.py (JWKS cache + RS256), security/deps.py get_current_user() [TDD]
- [x] 01-03-PLAN.md — RBAC Gate 2 + Tool ACL Gate 3 + audit logging: security/rbac.py, security/acl.py, ToolAcl migration [TDD]
- [x] 01-04-PLAN.md — FastAPI routes (/health, /api/agents/chat), frontend API client, Phase 1 verification checkpoint

### Phase 2: Agent Core and Conversational Chat
**Goal**: Users can have a natural language conversation with a streaming AI agent that remembers the conversation, routes through LiteLLM, and has isolated per-user memory
**Depends on**: Phase 1
**Requirements**: AGNT-01, AGNT-02, AGNT-07, MEMO-01, MEMO-05, INTG-04
**Success Criteria** (what must be TRUE):
  1. User can send a message in the web chat and see tokens stream back in real-time via AG-UI protocol
  2. Master agent receives user messages, creates a plan, and can delegate tasks (delegation targets available in Phase 3)
  3. Agent conversation turns are stored per user and per conversation -- user can resume a previous conversation with context preserved
  4. All LLM calls route through LiteLLM Proxy using model aliases (blitz/master, blitz/fast) -- no direct provider SDK calls
  5. User A cannot see User B's conversation history or memory (isolation enforced at query level)
**Plans**: 5 plans

Plans:
- [x] 02-01-PLAN.md — TDD: LiteLLM config general_settings + verify get_llm() contract for all 4 aliases (Wave 1)
- [x] 02-02-PLAN.md — TDD: BlitzState TypedDict + LangGraph master agent with routing conditional stub + CopilotKit runtime + /api/copilotkit endpoint with 3-gate security (Wave 2)
- [x] 02-03-PLAN.md — TDD: Short-term memory DB migration + core/context.py conversation_id injection + memory/short_term.py isolation + master agent memory nodes with dedup guard + GET /api/conversations (Wave 3, backend only)
- [x] 02-04-PLAN.md — TDD: AES-256-GCM encrypt/decrypt vault + user_credentials migration + GET /api/credentials + DELETE /api/credentials/{provider} (Wave 2, parallel with 02-02)
- [x] 02-05-PLAN.md — Frontend chat UI (proxy route + ChatLayout + CopilotKit streaming) + custom instructions DB/API/system-prompt injection + browser verification checkpoint (Wave 4)

### Phase 2.1: Tech Debt Cleanup (INSERTED)
**Goal**: Close all fixable tech debt items from the v1.0 milestone audit before beginning sub-agent work
**Depends on**: Phase 2
**Requirements**: None (non-requirement cleanup)
**Gap Closure:** Closes tech debt items from v1.0-MILESTONE-AUDIT.md
**Success Criteria** (what must be TRUE):
  1. All 5 affected frontend routes use a single consistent env var for the backend URL
  2. `user_instructions.updated_at` updates correctly on PUT (migration applied, onupdate set)
  3. REQUIREMENTS.md traceability table reflects actual completion status (12 checkboxes updated)
  4. ROADMAP.md plan checkboxes are accurate
**Plans**: 1 plan

Plans:
- [x] 02.1-01-PLAN.md — BACKEND_URL fix (5 routes), user_instructions.updated_at migration + onupdate, REQUIREMENTS.md + ROADMAP.md doc fixes

### Phase 3: Sub-Agents, Memory, and Integrations
**Goal**: The agent can perform real work -- fetch email, check calendars, query CRM, remember user preferences across sessions -- making it genuinely useful for daily routines
**Depends on**: Phase 2
**Requirements**: AGNT-03, AGNT-04, AGNT-05, AGNT-06, AGNT-08, MEMO-02, MEMO-03, MEMO-04, INTG-01, INTG-02, INTG-03, INTG-05
**Success Criteria** (what must be TRUE):
  1. User can ask "summarize my unread emails" and receive a structured email summary from the email sub-agent
  2. User can ask "what's on my calendar today?" and receive today's schedule with conflict detection from the calendar sub-agent
  3. User can ask "what's the status of Project X?" and the project sub-agent queries CRM via MCP to return structured results
  4. Old conversations are summarized into episode summaries; user preferences and facts accumulate as long-term memory with semantic search
  5. Agent responses include rich UI components (cards, tables, progress indicators) via A2UI when appropriate
**Plans**: 6 plans

Plans:
- [ ] 03-00-PLAN.md — Settings infrastructure: system_config + mcp_servers DB tables, admin config API, Settings → Agents toggle + Integrations stub (Wave 1, parallel with 03-01)
- [ ] 03-01-PLAN.md — Celery + bge-m3 embedding pipeline: celery_app, BGE_M3Provider, embed_and_store task, memory_episodes + memory_facts migration (Wave 1, parallel with 03-00)
- [ ] 03-02-PLAN.md — Medium + long-term memory: medium_term.py, long_term.py, master agent memory injection + Celery dispatch (Wave 2, depends on 03-01)
- [ ] 03-03-PLAN.md — MCP framework + CRM mock: MCPClient, MCPToolRegistry, 3-gate gated call, Settings → Integrations live CRUD, mcp-crm Docker service (Wave 2, depends on 03-00)
- [ ] 03-04-PLAN.md — Sub-agents + DeliveryRouterNode: email/calendar/project agents, intent router, DeliveryTarget enum, master agent routing update (Wave 3, depends on 03-02 + 03-03)
- [ ] 03-05-PLAN.md — A2UI components + useMcpTool + Settings pages: CalendarCard, EmailSummaryCard, ProjectStatusWidget, A2UIMessageRenderer, useMcpTool hook, POST /api/tools/call, Settings → Memory + Chat Preferences (Wave 4, depends on 03-04)

### Phase 3.1: Memory Read Path & MCP Hot-Registration (INSERTED)
**Goal**: Close the two integration gaps found in the v1.0 milestone audit — wire medium-term episode summaries into agent context, and make newly registered MCP servers immediately available without a backend restart
**Depends on**: Phase 3
**Requirements**: MEMO-02, INTG-01
**Gap Closure:** Closes gaps from v1.0-MILESTONE-AUDIT.md
**Success Criteria** (what must be TRUE):
  1. After a conversation is summarized by Celery, the episode summary is injected into the agent's context at the start of the next session
  2. After `POST /api/admin/mcp-servers` registers a new server, its tools are immediately callable via `POST /api/tools/call` without restarting the backend
  3. `pytest backend/tests/` passes with 0 failures (stale test_create_master_graph_has_routing_conditional fixed)
**Plans**: 1 plan

Plans:
- [ ] 03.1-01-PLAN.md — TDD: 3 failing tests (RED), episode injection in _load_memory_node (MEMO-02), MCPToolRegistry.refresh() in create_mcp_server() (INTG-01), full suite green

### Phase 4: Canvas and Workflows
**Goal**: Users can visually build multi-step automations on a drag-and-drop canvas that compile to executable agent workflows with human approval gates
**Depends on**: Phase 3
**Requirements**: WKFL-01, WKFL-02, WKFL-03, WKFL-04, WKFL-05, WKFL-06, WKFL-07, WKFL-08, WKFL-09
**Success Criteria** (what must be TRUE):
  1. User can drag nodes onto a React Flow canvas, connect them with edges, and save the workflow with schema_version in definition_json
  2. A saved canvas workflow compiles to a LangGraph StateGraph and executes end-to-end (nodes fire in sequence, data passes between them)
  3. User can create and run a Morning Digest workflow (Email Fetch -> Summarize -> Send to Channel) from a pre-built template
  4. User can create and run an Alert workflow (Trigger keyword -> Create Task -> Notify) from a pre-built template
  5. Workflow pauses at HITL approval nodes and waits for human input via A2UI before continuing
**Plans**: TBD

Plans:
- [ ] 04-01: React Flow canvas UI with node palette and workflow CRUD
- [ ] 04-02: Canvas-to-StateGraph compiler and execution engine
- [ ] 04-03: Workflow triggers (cron scheduling and webhook/events)
- [ ] 04-04: HITL approval nodes and A2UI integration
- [ ] 04-05: Pre-built workflow templates (Morning Digest, Alert)

### Phase 5: Scheduler and Channels
**Goal**: Users can interact with the agent from Telegram, WhatsApp, and MS Teams in addition to web chat, and workflows run on cron schedules as the owning user's context
**Depends on**: Phase 3 (can run in parallel with Phase 4)
**Requirements**: CHAN-01, CHAN-02, CHAN-03, CHAN-04, CHAN-05, CHAN-06
**Success Criteria** (what must be TRUE):
  1. User can send a message to the Blitz Telegram bot and receive agent responses with full tool access
  2. User can interact with the agent via WhatsApp Business and receive the same capabilities as web chat
  3. User can interact with the agent via MS Teams with the same capabilities as web chat
  4. External platform user IDs (Telegram, WhatsApp, Teams) are mapped to Blitz user IDs via channel_accounts table -- unlinked users receive a pairing prompt
  5. New channel adapters can be added by implementing the ChannelAdapter protocol without modifying agent, tool, or memory code
**Plans**: TBD

Plans:
- [ ] 05-01: ChannelAdapter protocol and channel gateway
- [ ] 05-02: Telegram channel adapter
- [ ] 05-03: WhatsApp Business channel adapter
- [ ] 05-04: MS Teams channel adapter
- [ ] 05-05: Channel identity resolution and session continuity

### Phase 6: Extensibility Registries
**Goal**: Admins and developers can manage the platform's agents, tools, skills, and MCP servers as runtime artifacts through database-backed registries with granular permissions
**Depends on**: Phases 4 and 5 (all artifact types exist to register)
**Requirements**: EXTD-01, EXTD-02, EXTD-03, EXTD-04, EXTD-05, EXTD-06
**Success Criteria** (what must be TRUE):
  1. Every agent, tool, skill, and MCP server has a database registry entry with name, description, version, status (enabled/disabled), and required permissions
  2. Admin can add, edit, disable, and re-enable any artifact via API -- disabled artifacts are unavailable to agents
  3. Developer can register a new tool or MCP server and it becomes available to authorized users without restarting the backend
  4. Permissions can be assigned per artifact per role -- e.g., "employee" role can use email tools but not sandbox tools
  5. Removing an artifact from the registry prevents all future invocations; existing running workflows using that artifact complete gracefully
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
  1. Untrusted code submitted by an agent executes in a Docker container with enforced CPU, memory, and network limits
  2. Sandbox containers have zero access to the host filesystem -- verified by attempting to read host paths
  3. Sandbox containers are destroyed after execution completes or after timeout, with no resource leaks
  4. Cross-user memory isolation is verified by automated penetration tests (User A cannot query User B's memory through any code path)
  5. PostgreSQL Row Level Security policies enforce user_id isolation as defense-in-depth beyond application-level checks
**Plans**: TBD

Plans:
- [ ] 07-01: Docker sandbox executor with resource limits and cleanup
- [ ] 07-02: Security hardening (RLS, credential scanning, pen tests)

### Phase 8: Observability
**Goal**: Operations team can monitor system health, agent performance, LLM costs, and troubleshoot issues through centralized dashboards and log aggregation
**Depends on**: Phase 7
**Requirements**: OBSV-01, OBSV-02, OBSV-03
**Success Criteria** (what must be TRUE):
  1. Grafana dashboards show real-time system health (service up/down, request latency, error rates) and agent performance (response time per agent, tool usage frequency)
  2. All service logs are aggregated in Loki via Alloy and searchable by service, user_id, tool name, and time range
  3. LiteLLM cost tracking dashboard shows cumulative and per-request spend broken down by model alias and by user
**Plans**: TBD

Plans:
- [ ] 08-01: Grafana and Loki setup with Alloy log collection
- [ ] 08-02: Dashboards for system health, agent performance, and LLM costs

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 (parallel with 5) -> 5 -> 6 -> 7 -> 8
Note: Phases 4 and 5 can execute in parallel as they share no mutual dependencies.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Identity and Infrastructure Skeleton | 4/4 | Complete    | 2026-02-24 |
| 2. Agent Core and Conversational Chat | 5/5 | Complete     | 2026-02-25 |
| 2.1. Tech Debt Cleanup (INSERTED) | 1/1 | Complete     | 2026-02-26 |
| 3. Sub-Agents, Memory, and Integrations | 6/7 | In Progress|  |
| 3.1. Memory Read Path & MCP Hot-Registration (INSERTED) | 0/1 | Not started | - |
| 4. Canvas and Workflows | 0/5 | Not started | - |
| 5. Scheduler and Channels | 0/5 | Not started | - |
| 6. Extensibility Registries | 0/3 | Not started | - |
| 7. Hardening and Sandboxing | 0/2 | Not started | - |
| 8. Observability | 0/2 | Not started | - |
