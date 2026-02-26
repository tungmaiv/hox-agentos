# Requirements: Blitz AgentOS

**Defined:** 2026-02-24
**Core Value:** Every Blitz employee gets an intelligent, context-aware assistant that automates daily work routines and lets them build custom automations without writing code — all within an enterprise-secure, on-premise environment.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Authentication

- [x] **AUTH-01**: User can log in via Keycloak SSO (OIDC Authorization Code flow)
- [x] **AUTH-02**: Backend validates JWT signature, expiry, issuer, and audience on every request
- [x] **AUTH-03**: User roles from Keycloak map to platform permissions (admin, developer, employee, viewer)
- [x] **AUTH-04**: Every tool call passes 3-gate security: JWT → RBAC → Tool ACL
- [x] **AUTH-05**: Every tool invocation is audit-logged with user_id, tool name, allowed/denied, duration_ms
- [x] **AUTH-06**: Credentials (access_token, refresh_token, password) are never logged, returned to frontend, or passed to LLMs

### Agents

- [x] **AGNT-01**: User can send natural language messages and receive streaming responses via AG-UI chat
- [x] **AGNT-02**: Master agent plans multi-step tasks and delegates to specialized sub-agents
- [x] **AGNT-03**: Email sub-agent can fetch, summarize, and draft email responses
- [x] **AGNT-04**: Calendar sub-agent can list events, summarize day's schedule, and detect conflicts
- [x] **AGNT-05**: Project sub-agent can query project status, create tasks, and update task status via MCP
- [x] **AGNT-06**: Channel sub-agent can route messages to appropriate delivery channel
- [x] **AGNT-07**: All LLM calls route through LiteLLM Proxy using model aliases (blitz/master, blitz/fast, blitz/coder, blitz/summarizer)
- [x] **AGNT-08**: Agent responses include generative UI (A2UI) components: cards, tables, forms, progress indicators

### Memory

- [x] **MEMO-01**: System stores conversation turns per user and conversation (short-term memory)
- [ ] **MEMO-02**: System summarizes old conversations into episode summaries (medium-term memory)
- [x] **MEMO-03**: System accumulates user preferences and facts with pgvector embeddings (long-term memory)
- [x] **MEMO-04**: Semantic search retrieves relevant facts for agent context via bge-m3 embeddings (1024-dim)
- [x] **MEMO-05**: All memory queries are parameterized on user_id from JWT — no cross-user reads

### Workflows

- [ ] **WKFL-01**: User can build workflows by dragging and dropping nodes on a React Flow canvas
- [ ] **WKFL-02**: Canvas workflows compile to LangGraph StateGraphs and execute end-to-end
- [ ] **WKFL-03**: User can create a morning digest workflow: Email Fetch → Summarize → Send to Channel
- [ ] **WKFL-04**: User can create an alert workflow: Trigger (keyword) → Create Task → Notify
- [ ] **WKFL-05**: Workflows support HITL approval nodes that pause and wait for human input via A2UI
- [ ] **WKFL-06**: Workflows can be triggered by cron schedules (e.g., "every weekday at 8 AM")
- [ ] **WKFL-07**: Workflows can be triggered by webhook/external events
- [ ] **WKFL-08**: Every workflow definition_json carries schema_version for migration safety
- [ ] **WKFL-09**: Pre-built workflow templates are available as starting points

### Integration

- [ ] **INTG-01**: MCP servers connect via HTTP+SSE transport and are registered in the tool registry
- [x] **INTG-02**: CRM mock MCP server provides sample tools (search leads, get contact) to validate the pattern
- [x] **INTG-03**: MCP tools go through the same 3-gate security as backend tools
- [x] **INTG-04**: User OAuth tokens are stored AES-256 encrypted in PostgreSQL, resolved internally by user_id
- [x] **INTG-05**: Email/calendar tools use provider-agnostic abstraction layer (pluggable Google/M365)

### Channels

- [ ] **CHAN-01**: User can interact with the agent via web chat (primary interface)
- [ ] **CHAN-02**: User can interact with the agent via Telegram
- [ ] **CHAN-03**: User can interact with the agent via WhatsApp
- [ ] **CHAN-04**: User can interact with the agent via MS Teams
- [ ] **CHAN-05**: Channel adapters follow a pluggable ChannelAdapter protocol for extensibility
- [ ] **CHAN-06**: External user IDs are mapped to Blitz user IDs via channel_accounts table

### Extensibility

- [ ] **EXTD-01**: Agents are registered in a database-backed registry with name, description, status, required permissions
- [ ] **EXTD-02**: Tools are registered in a database-backed registry with name, description, status, required permissions, sandbox flag
- [ ] **EXTD-03**: Skills are registered in a database-backed registry with name, description, status, required permissions
- [ ] **EXTD-04**: MCP servers are registered in a database-backed registry with name, URL, status, available tools
- [ ] **EXTD-05**: Admin and developer roles can add, edit, disable, and remove artifacts via API
- [ ] **EXTD-06**: Permissions can be assigned per artifact per role

### Sandbox

- [ ] **SBOX-01**: Untrusted code executes in Docker containers with CPU, memory, and network limits
- [ ] **SBOX-02**: Sandbox containers have no host filesystem access
- [ ] **SBOX-03**: Sandbox containers are destroyed after execution with timeout-based cleanup

### Observability

- [ ] **OBSV-01**: Grafana dashboards display system health, agent performance, and tool usage metrics
- [ ] **OBSV-02**: Loki aggregates structured JSON logs from all services via Alloy
- [ ] **OBSV-03**: LiteLLM cost tracking dashboard shows spend per model, per user

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Admin UI

- **ADUI-01**: Admin dashboard UI for managing agents, tools, skills, MCP servers
- **ADUI-02**: Visual interface for permission assignment and role management

### Advanced Canvas

- **ACNV-01**: Conditional branching in workflows (if/else nodes)
- **ACNV-02**: Loop nodes in workflows (repeat until condition)
- **ACNV-03**: Sub-workflow nesting (workflow as a node in another workflow)
- **ACNV-04**: Workflow version history with rollback

### Knowledge Base

- **KNBS-01**: Document ingestion pipeline for company knowledge (PDF, Docs)
- **KNBS-02**: RAG-based document search separate from agent memory

### Infrastructure

- **INFR-01**: Kubernetes deployment manifests (Helm charts)
- **INFR-02**: A2A protocol integration for external agent systems

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| SaaS/cloud hosting | Enterprise on-premise requirement — no external data processing |
| Kubernetes for MVP | Docker Compose sufficient for ~100 users; K8s adds operational overhead without benefit |
| HashiCorp Vault | AES-256 DB encryption sufficient at ~100 user scale; Vault adds infra complexity |
| Separate vector DB (Qdrant, Weaviate) | pgvector in PostgreSQL handles 100-user scale; same-query isolation via WHERE user_id |
| User self-service MCP registration | Security risk — 41% of MCP servers lack auth; admin-managed only |
| Real-time collaborative canvas editing | CRDT/OT complexity unjustified for ~100 users; single-user editing with workflow versioning |
| Mobile native apps | Web + Telegram/WhatsApp provide mobile access; native apps are a separate project |
| OAuth social login (Google/GitHub) | Keycloak SSO covers enterprise identity; social login is consumer-facing |
| "AI builds AI" self-modifying agents | Unsolved safety problem; agents cannot modify agent registry or create new agents |
| Voice interface | Massive scope increase for uncertain value; defer post-MVP |
| A2A protocol | Early-stage; no external agents to connect to yet |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 1 | Done |
| AUTH-02 | Phase 1 | Done |
| AUTH-03 | Phase 1 | Done |
| AUTH-04 | Phase 1 | Done |
| AUTH-05 | Phase 1 | Done |
| AUTH-06 | Phase 1 | Done |
| AGNT-01 | Phase 2 | Done |
| AGNT-02 | Phase 2 | Done |
| AGNT-07 | Phase 2 | Done |
| MEMO-01 | Phase 2 | Done |
| MEMO-05 | Phase 2 | Done |
| INTG-04 | Phase 2 | Done |
| AGNT-03 | Phase 3 | Complete |
| AGNT-04 | Phase 3 | Complete |
| AGNT-05 | Phase 3 | Complete |
| AGNT-06 | Phase 3 | Complete |
| AGNT-08 | Phase 3 | Complete |
| MEMO-02 | Phase 3.1 | Pending |
| MEMO-03 | Phase 3 | Complete |
| MEMO-04 | Phase 3 | Complete |
| INTG-01 | Phase 3.1 | Pending |
| INTG-02 | Phase 3 | Complete |
| INTG-03 | Phase 3 | Complete |
| INTG-05 | Phase 3 | Complete |
| WKFL-01 | Phase 4 | Pending |
| WKFL-02 | Phase 4 | Pending |
| WKFL-03 | Phase 4 | Pending |
| WKFL-04 | Phase 4 | Pending |
| WKFL-05 | Phase 4 | Pending |
| WKFL-06 | Phase 4 | Pending |
| WKFL-07 | Phase 4 | Pending |
| WKFL-08 | Phase 4 | Pending |
| WKFL-09 | Phase 4 | Pending |
| CHAN-01 | Phase 5 | Pending |
| CHAN-02 | Phase 5 | Pending |
| CHAN-03 | Phase 5 | Pending |
| CHAN-04 | Phase 5 | Pending |
| CHAN-05 | Phase 5 | Pending |
| CHAN-06 | Phase 5 | Pending |
| EXTD-01 | Phase 6 | Pending |
| EXTD-02 | Phase 6 | Pending |
| EXTD-03 | Phase 6 | Pending |
| EXTD-04 | Phase 6 | Pending |
| EXTD-05 | Phase 6 | Pending |
| EXTD-06 | Phase 6 | Pending |
| SBOX-01 | Phase 7 | Pending |
| SBOX-02 | Phase 7 | Pending |
| SBOX-03 | Phase 7 | Pending |
| OBSV-01 | Phase 8 | Pending |
| OBSV-02 | Phase 8 | Pending |
| OBSV-03 | Phase 8 | Pending |

**Coverage:**
- v1 requirements: 51 total
- Mapped to phases: 51
- Unmapped: 0
- Completed (v1.0, phases 1–3): 22 (AUTH-01–06, AGNT-01–08, MEMO-01, MEMO-03, MEMO-04, MEMO-05, INTG-02, INTG-03, INTG-04, INTG-05)
- Pending gap closure (phase 3.1): 2 (MEMO-02, INTG-01)
- Pending: 39

---
*Requirements defined: 2026-02-24*
*Last updated: 2026-02-26 after v1.0 audit — 12 completed requirements marked Done*
