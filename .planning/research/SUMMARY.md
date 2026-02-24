# Project Research Summary

**Project:** Blitz AgentOS
**Domain:** Enterprise on-premise agentic operating system
**Researched:** 2026-02-24
**Confidence:** HIGH

## Executive Summary

Blitz AgentOS is an enterprise-grade, on-premise agentic operating system designed for ~100 users at a Vietnamese company. The industry-standard approach for building this type of platform in 2025-2026 is a five-layer architecture: frontend (Next.js + AG-UI protocol), security gateway (Keycloak + 3-gate pipeline), agent orchestration (LangGraph supervisor pattern with sub-agents), tools/memory/LLM infrastructure (pgvector, MCP, LiteLLM), and supporting services (Celery, Redis, Docker). Every major technology choice is validated at GA-stable versions with high compatibility between components. The stack is opinionated and locked -- there are no open technology debates remaining.

The recommended approach is to build security and identity first (Keycloak SSO, JWT validation, RBAC), then the agent core (master agent, tool registry, 3-tier memory), then the visual canvas workflow builder, and finally channels and hardening. This ordering is dictated by strict dependency chains: agents need security context, tools need the registry, canvas needs working agents, channels need identity resolution. Phases 3 (Canvas) and 4 (Channels/Scheduler) can run in parallel since they share no mutual dependencies. The core value proposition -- "intelligent assistant that automates daily work via chat and visual workflows" -- is validated by Phase 3 completion.

The top risks are: (1) LangGraph agent infinite loops and context window explosion during multi-turn conversations, (2) credential leakage to LLMs through tool error messages, state serialization, or logging, (3) memory isolation bypass via workspace-scoped queries that omit the user_id filter, and (4) LiteLLM proxy as a single point of failure with silent cost explosion when falling back from local Ollama to cloud providers. All four are preventable with specific technical measures documented in PITFALLS.md, but they must be addressed in the phase where the risk first materializes -- not deferred to a hardening phase.

## Key Findings

### Recommended Stack

The stack is fully specified with locked versions and high confidence. All core technologies are at GA-stable releases with verified compatibility. One notable update from the architecture document: the MCP specification deprecated SSE transport in favor of Streamable HTTP (spec version 2025-03-26). The MCP Python SDK 1.26.x supports both, so migration is backward-compatible, but all new MCP servers should use Streamable HTTP.

**Core technologies:**
- **LangGraph 1.0.9:** Agent graph orchestration -- v1.0 GA with built-in persistence, HITL interrupts, and checkpointing; graph-based design maps directly to React Flow canvas
- **CopilotKit 1.51.x:** AG-UI protocol implementation -- real-time agent streaming, tool call visualization, CoAgent state sync with LangGraph
- **React Flow 12.10.x:** Visual workflow canvas -- native node/edge JSON format IS the workflow definition (no translation layer)
- **FastAPI 0.115+:** Async backend with Pydantic v2 integration, dependency injection for security gates
- **Keycloak 26.5.x:** Identity and SSO -- already deployed, zero new infrastructure cost
- **PostgreSQL 16 + pgvector 0.8:** Single database for relational + vector data; memory isolation via `WHERE user_id = $1` in the same query as vector search
- **bge-m3 (BAAI):** Multilingual embeddings (1024-dim) -- Vietnamese support built-in, self-hosted for on-premise compliance
- **LiteLLM Proxy 1.81.x:** Unified LLM gateway with model aliases, fallback routing, cost tracking
- **Celery 5.6.2 + Redis 7.x:** Task queue for embeddings and scheduled workflows

**Critical version note:** Next.js 16 is GA but CopilotKit compatibility is not yet confirmed. Start with Next.js 15.5+ (LTS) and upgrade after CopilotKit validates 16.x support.

### Expected Features

**Must have (table stakes -- Phases 1-3):**
- SSO via Keycloak with 3-gate security (JWT -> RBAC -> Tool ACL) on every request
- Conversational chat with AG-UI streaming and real-time token delivery
- Master agent with planning + sub-agent delegation (Email, Calendar)
- Tool execution with structured Pydantic I/O, registered in central tool registry
- 3-tier memory: short-term (conversation turns), medium-term (episode summaries), long-term (facts + pgvector embeddings)
- Visual workflow canvas (React Flow) compiling to LangGraph StateGraphs
- Cron-based job scheduling via Celery Beat
- Encrypted credential storage (AES-256 in PostgreSQL)
- Audit logging (structlog JSON, Loki-compatible)
- LLM provider abstraction (LiteLLM with Ollama-to-cloud fallback)
- One MCP server integration (CRM mock) to prove the pattern

**Should have (differentiators -- Phases 4-5):**
- Generative UI via A2UI (rich cards, forms, tables in chat)
- HITL approval nodes in canvas workflows
- Multi-channel presence (Telegram, WhatsApp, Teams) via ChannelAdapter protocol
- Docker sandbox for code execution with resource limits
- Long-term factual memory with semantic search

**Defer (v2+):**
- Admin dashboard UI, Kubernetes migration, advanced canvas (branching/loops/sub-workflows), A2A protocol, voice interface, knowledge base/document RAG, real-time collaborative canvas editing

### Architecture Approach

The architecture is a five-layer horizontal model with strict top-down communication. Security is enforced at a single gateway layer (Layer 2), agent logic never handles auth directly (Layer 3), and infrastructure is swappable (Layer 5). This mirrors Salesforce and AWS enterprise agentic architecture patterns, adapted for on-premise Docker Compose at ~100 user scale.

**Major components:**
1. **Security Runtime (FastAPI middleware)** -- JWT validation, RBAC check, Tool ACL enforcement; the single security perimeter for all requests
2. **Master Agent (LangGraph)** -- Supervisor pattern; receives all requests, plans multi-step tasks, delegates to domain sub-agents
3. **Workflow Engine (graphs.py)** -- Compiles React Flow canvas JSON directly to LangGraph StateGraphs; schema-versioned definitions with PostgreSQL checkpointer for durable execution
4. **Tool Registry (gateway/tool_registry.py)** -- Central catalog of all tools (backend, MCP, sandbox) with permissions metadata; single dispatch point
5. **Memory Subsystem** -- Three-tier PostgreSQL-based memory with pgvector; all queries enforce user_id isolation
6. **Channel Gateway** -- Pluggable adapter protocol for multi-channel message routing; identity resolution from external platform IDs to Blitz user IDs
7. **LLM Gateway (LiteLLM Proxy)** -- Single entry point for all LLM calls via model aliases; provider-agnostic with fallback routing

### Critical Pitfalls

1. **Agent infinite loops and context explosion** -- Set `recursion_limit` on every `graph.invoke()`, implement `trim_messages()` in state reducers, truncate tool outputs before appending to state. Must be addressed in Phase 2 from day one.

2. **Credential leakage to LLMs** -- Tools resolve credentials internally via user_id (never from parameters), wrap exceptions to strip local variables, add structlog redaction processor for token patterns. Architecture pattern in Phase 1, enforcement in Phase 2, automated scanning in Phase 5.

3. **Memory isolation bypass** -- All memory functions accept user_id from JWT only, never from tool input. Create a `MemoryQueryBuilder` that structurally prevents queries without user_id. Add PostgreSQL Row Level Security as defense-in-depth. Phase 2 core, Phase 5 hardening.

4. **LiteLLM as single point of failure with cost explosion** -- Configure per-model budget limits, per-user token budgets, Ollama health checks that distinguish slow from down, circuit breaker for cloud fallback. Phase 1 health checks, Phase 2 budgets, Phase 6 monitoring.

5. **Canvas workflow schema drift** -- Every `definition_json` must have `schema_version`, with a Pydantic validation model and numbered migration scripts. Establish the migration framework in Phase 3 before any workflow is saved.

## Implications for Roadmap

Based on combined research, the architecture has clear dependency chains that dictate a 6-phase build order. Phases 3 and 4 can run in parallel.

### Phase 1: Identity and Skeleton
**Rationale:** Security is the foundation everything else builds on. No agent, tool, or memory operation can function without JWT-validated user context. The infrastructure layer (PostgreSQL, Redis, Keycloak, LiteLLM) must be running before any application code is useful.
**Delivers:** Working SSO login, JWT validation, RBAC permission system, FastAPI skeleton with AG-UI runtime shell, Next.js frontend skeleton with CopilotKit provider, all Docker Compose services healthy.
**Addresses features:** SSO/Keycloak Auth, RBAC, basic audit logging, LiteLLM proxy setup.
**Avoids pitfalls:** Keycloak JWKS rotation (implement cache with TTL from day one), LiteLLM health checks and restart policies, Ollama `host.docker.internal` networking.
**Stack focus:** Keycloak 26.5, FastAPI 0.115, Next.js 15.5, CopilotKit 1.51, LiteLLM 1.81, PostgreSQL 16, Redis 7.x.

### Phase 2: Agents, Tools, and Memory
**Rationale:** The tool registry must exist before agents can do anything. Agents need memory context to function well. This phase delivers the core value: "talk to an agent that actually does things." This is the highest-risk phase because it introduces LLM interaction, tool execution, and memory -- all three areas with critical pitfalls.
**Delivers:** Working master agent with sub-agent delegation (email + calendar), tool registry with backend tools and one MCP server (CRM mock), 3-tier memory system with embedding pipeline, encrypted credential store for OAuth tokens.
**Addresses features:** Conversational chat (AG-UI streaming), master agent + sub-agents, tool execution, short/medium/long-term memory, MCP integration, credential encryption.
**Avoids pitfalls:** Agent infinite loops (recursion limits + trim_messages from day one), credential leakage (tool-level credential resolution, SafeException wrapper), memory isolation (MemoryQueryBuilder with mandatory user_id), bge-m3 Celery worker isolation (dedicated queue, --concurrency=1, pre-load model).
**Stack focus:** LangGraph 1.0.9, PydanticAI 1.63, bge-m3 + FlagEmbedding, MCP SDK 1.26, Celery 5.6.

### Phase 3: Canvas and Workflows
**Rationale:** The visual workflow builder is the core differentiator and requires working agents and tools as prerequisites. Canvas definition_json compiles directly to LangGraph StateGraphs -- this is the unique architecture bet. Schema versioning must be established before any workflow is persisted.
**Delivers:** React Flow canvas UI with drag-and-drop workflow building, compile_workflow_to_stategraph() compiler, workflow CRUD API, PostgreSQL checkpointer for durable execution, 2-3 starter workflow templates (Morning Digest, Alert, Meeting Prep), basic HITL approval nodes.
**Addresses features:** Visual workflow canvas, pre-built templates, HITL approval nodes, canvas-compiled StateGraphs.
**Avoids pitfalls:** Canvas schema drift (Pydantic validation model + migration framework from first save), checkpoint table bloat (set TTL policy early).
**Stack focus:** React Flow 12.10, LangGraph StateGraph + PostgresSaver, A2UI for HITL approval UI.

### Phase 4: Scheduler and Channels
**Rationale:** Can run in parallel with Phase 3. Scheduling validates the automation value proposition ("run this every morning at 8am"). Channel adapters are additive and independent once the ChannelAdapter protocol is defined. Note: WhatsApp Business verification takes 1-4 weeks -- start the process in Phase 1.
**Delivers:** Celery Beat cron scheduling with jobs running as owner's UserContext, Telegram channel adapter (first channel), channel identity resolution (external_user_id -> Blitz user_id), channel session continuity across platforms.
**Addresses features:** Cron scheduling, webhook/event triggers, multi-channel presence (Telegram first).
**Avoids pitfalls:** Scheduled jobs running as service account (enforce UserContext reconstruction), channel webhook authentication (verify platform-specific signatures), Telegram webhook URL (needs public HTTPS -- use ngrok for dev), unlinked user path (pairing request, not crash).
**Stack focus:** Celery Beat, python-telegram-bot, ChannelAdapter protocol.

### Phase 5: Hardening and Sandboxing
**Rationale:** Security hardening makes sense only after core features exist. This is the "tighten the bolts" phase -- Gate 3 ACL enforcement, Docker sandbox, additional channel adapters, and the automated security scanning that catches what manual code review misses.
**Delivers:** Docker sandbox execution with resource limits, Gate 3 Tool ACL enforcement (agui_middleware.py), MCP ACL integration, PostgreSQL Row Level Security policies, WhatsApp + Teams channel adapters, audit logging finalization, credential scanning in CI, cross-user penetration tests.
**Addresses features:** Docker sandbox, Tool ACL enforcement, WhatsApp + Teams channels, artifact registries (code-first CRUD).
**Avoids pitfalls:** Memory isolation bypass (RLS policies + pen tests), credential leakage (automated scanning in CI), Docker sandbox resource leaks (timeout-based cleanup), MCP connection resilience (pooling + health checks), checkpoint table growth (TTL-based cleanup task).
**Stack focus:** Docker SDK, structlog redaction processors, PostgreSQL RLS.

### Phase 6: Observability
**Rationale:** You cannot meaningfully monitor a system that does not yet exist. Observability is last because it requires understanding what to measure, which only becomes clear after the system is functional and handling real workloads.
**Delivers:** Grafana dashboards, Loki log aggregation via Alloy, LiteLLM cost tracking dashboard, performance tuning, load testing at 100-user scale.
**Addresses features:** Observability dashboards, cost monitoring, performance optimization.
**Avoids pitfalls:** LiteLLM cost explosion (spend dashboard + budget alerts), silent performance degradation (latency tracking per agent/tool/MCP call).
**Stack focus:** Grafana, Loki, Alloy, LiteLLM /spend/logs endpoint.

### Phase Ordering Rationale

- **Security before everything:** JWT/RBAC is the foundation. Every subsequent feature depends on authenticated UserContext. There is no shortcut here.
- **Tool registry before agents:** Agents without tools are just chatbots. The registry defines what agents CAN do and enforces what they are ALLOWED to do.
- **Memory alongside agents:** Agents need context (recent turns + relevant facts) to produce useful responses. Building memory after agents means the initial agent experience is poor, creating a bad first impression.
- **Canvas after agents:** You cannot build meaningful workflows without working tool execution. Canvas nodes reference tools from the registry.
- **Phases 3 and 4 are parallel:** Canvas/Workflows and Scheduler/Channels share no mutual dependencies. Both depend only on Phase 2 output. Assign to separate teams or interleave.
- **Hardening after features exist:** Security hardening (RLS, sandbox, automated scanning) validates that existing features are secure. Running these checks against incomplete features produces false results.
- **Observability is last:** Dashboards and monitoring are only useful when there is a running system producing meaningful metrics.

### Research Flags

**Phases likely needing deeper research during planning:**
- **Phase 2 (Agents, Tools, Memory):** Highest complexity and risk. LangGraph deep agent patterns, CopilotKit + LangGraph integration specifics (ZodError on ToolMessage for HITL), bge-m3 Celery worker memory management, MCP client connection pooling. Run `/gsd:research-phase` before planning.
- **Phase 3 (Canvas and Workflows):** Canvas-to-StateGraph compilation is the core architecture bet. React Flow v12 save/restore patterns, LangGraph PostgresSaver configuration (autocommit + dict_row), HITL interrupt/resume lifecycle. Run `/gsd:research-phase` before planning.
- **Phase 4 (Scheduler and Channels):** Telegram webhook setup (ngrok for dev, reverse proxy for prod), WhatsApp Business API verification timeline, channel identity resolution patterns. Moderate research needed.

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Identity and Skeleton):** Keycloak OIDC + FastAPI JWT middleware is well-documented. Docker Compose setup is standard. CopilotKit provider setup has official tutorials.
- **Phase 5 (Hardening):** PostgreSQL RLS, Docker sandbox resource limits, structlog processors -- all well-documented patterns. Focus on implementation, not research.
- **Phase 6 (Observability):** Grafana + Loki is a mature, well-documented stack. Standard setup.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All core technologies verified at GA versions via official docs and package registries. Compatibility matrix confirmed. One update needed: MCP transport should be Streamable HTTP, not SSE. |
| Features | HIGH | Grounded in competitor analysis (OpenClaw, Dify, n8n, Kore.ai) and architecture docs. Feature priorities are clear. Anti-features well-identified. |
| Architecture | HIGH | Five-layer model directly documented in architecture.md. Patterns verified against Salesforce, AWS, and LangChain enterprise references. Build order driven by clear dependency chains. |
| Pitfalls | HIGH | Verified across GitHub issues, official documentation, and multiple independent security/performance sources. Pitfall-to-phase mapping is concrete with testable verification criteria. |

**Overall confidence:** HIGH

### Gaps to Address

- **MCP Transport Migration:** Architecture doc specifies HTTP+SSE but MCP spec deprecated SSE. Update architecture to Streamable HTTP. The SDK supports both, so this is a configuration change, not a rewrite. Address during Phase 2 planning.
- **CopilotKit + Next.js 16 Compatibility:** Not yet confirmed. Start with Next.js 15.5 and monitor CopilotKit release notes. Address before any Next.js upgrade.
- **CopilotKit + LangGraph HITL Integration:** Known ZodError when using LangGraph tools for HITL approval (use graph interrupt nodes instead). Needs hands-on prototyping during Phase 3.
- **WhatsApp Business API Verification:** Takes 1-4 weeks. Start the process in Phase 1 even though the adapter is Phase 4/5. Not a technical gap but a process dependency.
- **Database-Backed Artifact Registries:** Architecture states code-first registry for MVP, database-backed later. The migration path is not yet detailed. Design during Phase 5 planning.
- **A2UI Maturity:** A2UI is in Public Preview (v0.8). CopilotKit's generative UI is the stable foundation; A2UI is the declarative format. Monitor for breaking changes.
- **IVFFlat Index Tuning:** Default `lists=100` is wrong for small fact tables (< 1000 rows). Start with `lists=10` or HNSW. Revisit when fact count grows. Address during Phase 2 implementation.

## Sources

### Primary (HIGH confidence)
- Blitz AgentOS architecture document (`docs/architecture/architecture.md`)
- Blitz AgentOS blueprint (`docs/design/blueprint.md`)
- Blitz AgentOS module breakdown (`docs/design/module-breakdown.md`)
- Blitz AgentOS implementation guide (`docs/implementation/implementation-guide.md`)
- LangGraph 1.0 official docs and PyPI (v1.0.9)
- CopilotKit npm (v1.51.x) and AG-UI protocol docs
- React Flow v12 docs and npm (@xyflow/react 12.10.x)
- FastAPI release notes (0.115+)
- Keycloak 26.5 release notes
- pgvector 0.8.0 announcement and GitHub
- LiteLLM docs and PyPI (v1.81.x)
- MCP specification (2025-03-26 transport update)
- bge-m3 HuggingFace model card and FlagEmbedding PyPI
- LangGraph persistence and checkpointing docs
- PostgresSaver configuration requirements

### Secondary (MEDIUM confidence)
- AG-UI protocol specification (docs.ag-ui.com)
- A2UI specification (Google, Public Preview v0.8)
- Salesforce Enterprise Agentic Architecture patterns
- OpenClaw architecture overview and feature list
- CopilotKit + LangGraph integration guides
- LiteLLM budget/rate limit and fallback documentation
- MCP enterprise adoption analysis (2026)
- OWASP LLM Top 10 (2025) and LLM security guides
- Celery vs Temporal comparison analysis

### Tertiary (needs validation during implementation)
- CopilotKit + LangGraph HITL ZodError workaround (community issue, not official fix)
- A2UI + CopilotKit rendering pipeline specifics (Public Preview, may change)
- bge-m3 memory requirements under concurrent Celery worker load (model-specific, needs profiling)
- LiteLLM circuit breaker configuration (community pattern, not official feature)

---
*Research completed: 2026-02-24*
*Ready for roadmap: yes*
