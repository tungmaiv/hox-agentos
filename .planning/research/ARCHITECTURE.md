# Architecture Patterns

**Domain:** Enterprise Agentic Operating System (on-premise, multi-agent, multi-channel)
**Researched:** 2026-02-24 (foundation) / 2026-03-05 (v1.3 integration addendum)

---

## Recommended Architecture

Blitz AgentOS follows a **five-layer horizontal architecture** with strict top-down communication. This is the established pattern for enterprise agentic platforms in 2025-2026, combining elements from the Salesforce Enterprise Agentic Architecture (orchestrator + worker + utility agents), the OpenClaw local-first pattern (sandboxed execution, hierarchical memory), and the emerging AG-UI protocol standard (event-driven frontend-to-agent communication).

```
LAYER 1: FRONTEND (Next.js + CopilotKit + React Flow)
    |
    | HTTPS + AG-UI SSE / REST (JWT attached)
    v
LAYER 2: SECURITY RUNTIME (FastAPI + Keycloak JWT + RBAC + Tool ACL)
    |
    | Authenticated internal calls (UserContext injected)
    v
LAYER 3: AGENT ORCHESTRATION (LangGraph Master Agent + Sub-Agents + Workflow Engine)
    |                    |                    |
    v                    v                    v
LAYER 4a:            LAYER 4b:            LAYER 4c:
TOOLS & SANDBOX      MEMORY SUBSYSTEM     LLM GATEWAY
(Backend tools,      (3-tier PostgreSQL   (LiteLLM Proxy ->
 MCP, Docker exec)    + pgvector)          Ollama/Cloud)
    |                    |                    |
    v                    v                    v
LAYER 5: INFRASTRUCTURE
(PostgreSQL+pgvector | Redis | Keycloak | Celery | Channel Gateways | MCP Servers | Audit Logs)
```

**Why this architecture:** The five-layer model cleanly separates concerns so that security is enforced at a single gateway (Layer 2), agent logic never handles auth (Layer 3), and infrastructure (Layer 5) is swappable. This mirrors the enterprise agentic architecture patterns recommended by Salesforce and AWS, adapted for on-premise Docker Compose deployment at ~100 user scale.

**Confidence:** HIGH -- this architecture is directly documented in `docs/architecture/architecture.md` and aligns with industry patterns confirmed across multiple sources.

---

### Component Boundaries

| Component | Responsibility | Communicates With | Protocol |
|-----------|---------------|-------------------|----------|
| **Frontend (Next.js + CopilotKit)** | AG-UI chat, A2UI generative widgets, React Flow canvas, Keycloak login | Backend (FastAPI) | HTTPS + AG-UI SSE, REST |
| **Security Runtime (FastAPI)** | JWT validation, RBAC check, Tool ACL enforcement, request routing | Keycloak (JWKS), Agent Orchestration, Tool Registry | Internal function calls |
| **Master Agent (LangGraph)** | Planning, sub-agent delegation, conversation handling | Sub-Agents, Tool Registry, Memory, LLM Gateway | LangGraph StateGraph transitions |
| **Sub-Agents (Email, Calendar, Project, Channel)** | Domain-specific task execution | Tools (via registry), Memory, LLM Gateway | LangGraph node invocation |
| **Workflow Engine (graphs.py)** | Compile canvas JSON to StateGraph, execute workflows | LangGraph StateGraph, PostgreSQL Checkpointer | Compiled graph execution |
| **Tool Registry (gateway/tool_registry.py)** | Central tool catalog with permissions metadata | Backend tools, MCP Client, Sandbox Executor | Direct function dispatch |
| **Backend Tools** | Email/Calendar/Project/DataOps operations | External APIs (via credentials), MCP servers | HTTP/SDK calls |
| **MCP Client** | Proxy calls to MCP servers | MCP Servers (CRM, Docs) | HTTP+SSE (MCP standard) |
| **Docker Sandbox** | Isolated execution of untrusted code | Docker daemon | Docker SDK |
| **Memory Subsystem** | 3-tier memory (short/medium/long term) | PostgreSQL + pgvector, Celery (embedding) | SQL queries, async tasks |
| **LLM Gateway (LiteLLM)** | Unified LLM API, model routing, fallback | Ollama, Anthropic, OpenAI, OpenRouter | OpenAI-compatible API |
| **Celery Workers** | Embedding jobs, scheduled workflow execution | Redis (broker), PostgreSQL, LLM Gateway | Celery task protocol |
| **Channel Gateway** | Inbound/outbound message routing, identity resolution | Channel Adapters, Agent Runtime, PostgreSQL | Internal API + webhooks |
| **Channel Adapters** | Platform-specific message conversion | External platforms (Telegram, WhatsApp, Teams) | Platform webhooks/APIs |
| **Audit Logger** | Structured JSONL logging of all security events | File system (Loki-ready) | structlog JSON |

### Data Flow

#### 1. Chat Request (Web UI)

```
User (Browser)
  |-- AG-UI request + JWT --> Next.js /api/copilotkit
  |-- Proxy --> FastAPI /api/copilotkit
  |                |
  |          Gate 1: JWT validation (keycloak JWKS)
  |          Gate 2: RBAC permission check
  |                |
  |          UserContext injected
  |                |
  |          master_agent.run_conversation()
  |                |
  |          1. Load short-term memory (last N turns)
  |          2. Vector search long-term facts (pgvector)
  |          3. LLM call via LiteLLM (blitz/master alias)
  |          4. Agent decides: direct response OR delegate
  |                |
  |          [If tool call needed]:
  |                |
  |          Gate 3: Tool ACL check (agui_middleware.py)
  |                |
  |          tool_registry.dispatch(tool_name, params)
  |                |
  |          [If MCP tool]: mcp_client.call_tool(server, tool, params)
  |          [If sandbox]:  sandbox.executor.run(command)
  |          [If backend]:  direct function call
  |                |
  |          Audit log: user_id, tool, allowed, duration_ms
  |                |
  |          Response streamed via AG-UI SSE
  |                |
  |<-- AG-UI SSE tokens + A2UI JSONL envelopes
```

#### 2. Workflow Execution (Canvas or Scheduled)

```
Trigger: Manual (POST /api/workflows/{id}/run) OR Celery Beat (scheduled job)
  |
  Load Workflow.definition_json from DB
  |
  compile_workflow_to_stategraph(definition_json)
  |-- For each node in JSON:
  |     type=agent  -> _build_agent_node()  (wraps sub-agent)
  |     type=tool   -> _build_tool_node()   (wraps tool call + ACL)
  |     type=mcp    -> _build_mcp_node()    (wraps MCP client)
  |     type=hitl   -> _build_hitl_node()   (renderAndWait pause)
  |
  Execute StateGraph with PostgreSQL checkpointer
  |-- State saved after each node (durable execution)
  |-- HITL node: pauses, persists, waits for user approval
  |-- On resume: loads checkpoint, continues from pause point
  |
  Persist WorkflowRun (status, state_snapshot, timestamps)
  |
  Deliver result via channel_dispatcher (web notification, Telegram, etc.)
```

#### 3. Channel Inbound Message (e.g., Telegram)

```
Telegram webhook -> POST /channels/telegram/webhook
  |
  telegram_adapter.parse(update) -> InternalMessage
  |
  channel_gateway.handle_inbound(msg)
  |-- _enrich_identity(): lookup channel_accounts table
  |   (external_user_id -> Blitz user_id)
  |-- _check_pairing(): enforce allowlist/connection rules
  |-- _route_to_agent(): call master_agent.run_conversation()
  |   with user_context from resolved identity
  |
  Agent processes, generates response
  |
  channel_gateway.send_outbound(response_msg)
  |-- adapter.send(): format for Telegram API, send
  |   (full message only, no streaming chunks)
```

#### 4. Memory Lifecycle

```
User sends message
  |
  [Write] short_term.append_turn(user_id, conversation_id, role, content)
  |
  [Read] short_term.get_recent_turns(user_id, conversation_id, n=20)
  |       -> Injected into LLM prompt as conversation context
  |
  [Read] long_term.memory_search(user_id, query_embedding)
  |       -> pgvector cosine similarity search
  |       -> WHERE user_id = $1 (isolation enforced)
  |       -> Top-k relevant facts injected into prompt
  |
  [Trigger] When token count > threshold OR session ends:
  |       summarizer.summarize_turns() via LLM (blitz/summarizer)
  |       -> medium_term.create_episode(user_id, summary, tags)
  |
  [Trigger] When new fact extracted by agent:
  |       long_term.write_fact(user_id, scope, subject, content)
  |       -> Celery task: indexer.embed_fact(fact_id)
  |       -> EmbeddingService.embed(content) using bge-m3
  |       -> UPDATE memory_facts SET embedding = $vec WHERE id = $id
```

---

## Patterns to Follow

### Pattern 1: Three-Gate Security Pipeline

**What:** Every request passes through JWT validation, RBAC permission check, and Tool ACL check in strict sequence. No gate can be skipped.

**When:** Every AG-UI request, every REST API call, every tool invocation (including MCP tools and scheduled jobs).

**Why:** Enterprise security requires defense in depth. Gate 1 verifies identity, Gate 2 verifies role-level authorization, Gate 3 verifies tool-specific access. Separating these prevents a bug in one gate from compromising the others.

```python
# security/deps.py -- FastAPI dependency chain
async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserContext:
    """Gate 1: JWT validation"""
    claims = await jwt.decode_token(token)  # JWKS verify, check exp/iss/aud
    user = await user_repo.get_by_keycloak_id(claims.sub)
    return UserContext(user_id=user.id, roles=claims.realm_access.roles)

def require_permission(permission: str):
    """Gate 2: RBAC check"""
    async def dependency(user: UserContext = Depends(get_current_user)):
        if not await rbac.has_permission(user, permission):
            raise HTTPException(403, f"Missing permission: {permission}")
        return user
    return dependency

# gateway/agui_middleware.py -- Gate 3 runs on TOOLCALL_START AG-UI event
async def check_tool_acl(tool_name: str, user_roles: list[str]) -> bool:
    """Gate 3: Tool ACL check"""
    acl = await acl_repo.get_tool_acl(tool_name)
    return any(role in acl.allowed_roles for role in user_roles)
```

**Confidence:** HIGH -- documented in architecture, aligns with established enterprise security patterns (Keycloak + FastAPI middleware verified across multiple sources).

---

### Pattern 2: Master Agent with Sub-Agent Delegation (Supervisor Pattern)

**What:** A single master agent receives all user requests, plans multi-step tasks, and delegates domain-specific work to specialized sub-agents. Each sub-agent has its own tool set and memory scope.

**When:** For any complex user request that spans multiple domains (e.g., "Check my emails, summarize the important ones, and block time on my calendar for follow-ups").

**Why:** The supervisor pattern is the dominant enterprise orchestration pattern in 2025-2026 (used by Salesforce Agentforce, AWS Multi-Agent, LangChain recommendations). It provides: (a) clear responsibility boundaries per domain, (b) centralized planning and progress tracking, (c) isolation of tool access per sub-agent, (d) natural mapping to canvas workflow nodes.

```python
# agents/master_agent.py
async def run_conversation(user_context: UserContext, message: str, channel: str):
    # 1. Load context
    turns = await short_term.get_recent_turns(user_context.user_id, conversation_id, n=20)
    facts = await long_term.memory_search(user_context.user_id, embed(message))

    # 2. Master agent plans (todo middleware forces explicit planning)
    # 3. Delegates to sub-agents as LangGraph nodes
    # 4. Streams response via AG-UI

# agents/subagents/email_agent.py
def create_email_agent(user_context: UserContext) -> CompiledGraph:
    tools = [fetch_emails, send_email, draft_reply]
    # Tools resolve credentials via user_context.user_id -- never tokens
    return create_react_agent(get_llm("blitz/master"), tools)
```

**Confidence:** HIGH -- LangGraph Deep Agent pattern is well-documented and the supervisor pattern is the industry standard for enterprise multi-agent systems.

---

### Pattern 3: Canvas-to-StateGraph Compilation

**What:** The React Flow canvas stores workflow definitions as JSON (nodes + edges). The backend compiles this JSON into a LangGraph StateGraph at execution time. The canvas JSON IS the source of truth -- no separate workflow definition language.

**When:** When a user creates or edits a workflow in the canvas, and when that workflow is executed (manually or by scheduler).

**Why:** Eliminating a translation layer between the visual canvas and the execution engine removes an entire class of bugs. React Flow's native node/edge JSON maps directly to LangGraph's `add_node`/`add_edge` API. The `schema_version` field enables safe migration when node types change.

```python
# agents/graphs.py
def compile_workflow_to_stategraph(definition: WorkflowDefinition) -> StateGraph:
    graph = StateGraph(BlitzState)
    node_builders = {
        "agent": _build_agent_node,   # wraps sub-agent invocation
        "tool":  _build_tool_node,    # wraps tool call with ACL
        "mcp":   _build_mcp_node,     # wraps MCP client call
        "hitl":  _build_hitl_node,    # renderAndWait pause
    }
    for node in definition["nodes"]:
        graph.add_node(node["id"], node_builders[node["type"]](node["data"]))
    for edge in definition["edges"]:
        if edge.get("condition"):
            graph.add_conditional_edges(edge["source"], ...)
        else:
            graph.add_edge(edge["source"], edge["target"])
    graph.set_entry_point(definition["entry_node"])
    # PostgreSQL checkpointer for HITL durability
    checkpointer = PostgresSaver.from_conn_string(settings.database_url)
    return graph.compile(checkpointer=checkpointer)
```

**Confidence:** HIGH -- this is the core pattern in the architecture document; LangGraph's StateGraph + PostgresSaver checkpointer for durable execution is a documented production pattern verified via LangChain official docs.

---

### Pattern 4: Per-User Memory Isolation via SQL Parameterization

**What:** Every memory query (short-term, medium-term, long-term/vector) includes `WHERE user_id = $1` where `user_id` comes exclusively from the JWT-validated UserContext. There is no API parameter to override user_id.

**When:** Every memory read and write operation, without exception.

**Why:** Because pgvector lives inside PostgreSQL, memory isolation is enforced in the same SQL query as the vector search. This eliminates the class of bugs where a vector DB query returns results across users. This is the critical security advantage of using pgvector over a separate vector DB.

```sql
-- Every memory query follows this pattern:
SELECT id, subject, title, content, scope, tags
FROM memory_facts
WHERE user_id = $user_id                           -- ALWAYS from JWT
  AND (workspace_id = $workspace_id OR workspace_id IS NULL)
ORDER BY embedding <-> $query_embedding            -- cosine distance
LIMIT $limit;
```

**Confidence:** HIGH -- this is an architecture invariant documented in CLAUDE.md and architecture.md; pgvector's ability to combine vector search with relational filtering in a single query is well-documented.

---

### Pattern 5: Pluggable Channel Adapter Protocol

**What:** A central Channel Gateway handles all inbound/outbound message routing. Each messaging platform (Telegram, WhatsApp, Teams) implements a `ChannelAdapter` protocol with a single `send()` method. Inbound webhooks convert platform-specific events to a canonical `InternalMessage` format.

**When:** Adding any new messaging channel to the system.

**Why:** The adapter pattern decouples platform-specific logic from the agent runtime. Adding a new channel requires: (1) add enum value, (2) implement adapter, (3) create webhook route, (4) register adapter. No changes to agent code, tool code, memory, or security.

```python
# channels/dispatcher.py
class ChannelAdapter(Protocol):
    channel: ChannelType
    async def send(self, msg: InternalMessage) -> None: ...

class ChannelGateway:
    def __init__(self, adapters: dict[ChannelType, ChannelAdapter]):
        self.adapters = adapters

    async def handle_inbound(self, msg: InternalMessage):
        msg = await self._enrich_identity(msg)   # external_id -> Blitz user_id
        if not await self._check_pairing(msg):    # allowlist/connection rules
            return
        await self._route_to_agent(msg)           # -> master_agent.run_conversation()

    async def send_outbound(self, msg: InternalMessage):
        adapter = self.adapters[msg.channel]
        await adapter.send(msg)
```

**Confidence:** HIGH -- this is a well-established GoF pattern applied to messaging systems; documented in the project's channel-integration design doc.

---

### Pattern 6: Database-Backed Artifact Registries

**What:** Agents, tools, skills, and MCP servers are registered in database tables with metadata (name, description, version, status, required permissions). This makes them data, not just code, enabling runtime management without redeployment.

**When:** Registering any new agent, tool, skill, or MCP server. When checking permissions during execution. When building the tool list for an agent.

**Why:** Code-only registration (e.g., Python decorators) requires redeployment to add/remove/disable capabilities. Database-backed registries allow: enable/disable without restart, permission assignment per role, versioning, and future admin UI without code changes.

```python
# gateway/tool_registry.py
TOOL_REGISTRY: dict[str, ToolMeta] = {
    "email.fetch": ToolMeta(
        fn=fetch_emails,
        description="Fetch user emails since a given timestamp",
        required_permissions=["tool:email.read"],
        sandbox_required=False,
    ),
    "mcp.crm.search_leads": ToolMeta(
        fn=mcp_call,
        description="Search CRM leads",
        required_permissions=["tool:crm.read"],
        sandbox_required=False,
        mcp_server="crm",
        mcp_tool="search_leads",
    ),
}
```

**Confidence:** MEDIUM -- the code-first registry (Python dict) is documented; database-backed registry is stated as a project goal in PROJECT.md but the migration path from code-first to DB-backed is not yet detailed. This is a common enterprise pattern but the specific implementation for this project will need to be designed during Phase 2 or Phase 5.

---

### Pattern 7: LLM Abstraction via Proxy with Model Aliases

**What:** All LLM calls go through a self-hosted LiteLLM Proxy. Agent code uses stable aliases (`blitz/master`, `blitz/fast`, `blitz/coder`) and never references provider-specific model names or SDKs.

**When:** Every LLM invocation in the entire system.

**Why:** Provider agnosticism -- swap Ollama for Claude by changing a YAML config, not code. Automatic fallback routing (local -> cloud). Cost tracking. Retry logic. Single point of configuration. This is critical for an on-premise system where the primary LLM (local Ollama) may be less reliable than cloud providers.

```python
# core/config.py -- THE ONLY WAY to get an LLM client
def get_llm(alias: str = "blitz/master") -> ChatOpenAI:
    return ChatOpenAI(
        model=alias,
        base_url=settings.litellm_url,   # http://litellm:4000
        api_key=settings.litellm_key,
        streaming=True,
    )
```

**Confidence:** HIGH -- LiteLLM is the standard proxy for multi-provider LLM routing; documented in architecture; config verified against LiteLLM documentation.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Direct Provider SDK Usage

**What:** Importing `anthropic`, `openai`, or other provider SDKs directly in agent/tool code.

**Why bad:** Locks agent code to a specific provider. Loses fallback routing, cost tracking, and retry logic. Cannot switch providers without code changes. Violates the LiteLLM proxy architecture.

**Instead:** Always use `get_llm(alias)` from `core/config.py`.

---

### Anti-Pattern 2: User ID from Request Body for Memory Queries

**What:** Accepting `user_id` as a request parameter for memory operations instead of extracting it from the JWT.

**Why bad:** Allows any authenticated user to read another user's memory by passing a different user_id. Completely breaks memory isolation -- the most critical security invariant.

**Instead:** Always extract `user_id` from `get_current_user()` (JWT-validated UserContext). Memory function signatures should make this explicit:

```python
# Correct: user_id is always from JWT
async def memory_search(user_id: UUID, query: str) -> list[Fact]:
    # user_id comes from get_current_user(), never from request body
```

---

### Anti-Pattern 3: Business Logic in Channel Adapters

**What:** Putting agent logic, memory access, or tool calls directly in a channel adapter.

**Why bad:** Duplicates logic across channels. New channels must re-implement business logic. Security checks may be inconsistent across channels. Testing requires mocking platform APIs.

**Instead:** Channel adapters only translate between platform-specific formats and `InternalMessage`. All business logic goes through `_route_to_agent()` which calls the standard `master_agent.run_conversation()`.

---

### Anti-Pattern 4: Skipping Schema Versioning on Canvas Workflows

**What:** Modifying the `WorkflowDefinition` node/edge schema without incrementing `schema_version` and writing a migration script.

**Why bad:** Existing saved workflows in the database become incompatible with the new compiler. Users lose their workflows. Runtime errors when executing old workflows.

**Instead:** Every `definition_json` has `schema_version: "1.0"`. Breaking changes require: (1) increment version, (2) write migration script, (3) update compiler to handle both versions.

---

### Anti-Pattern 5: Running Embeddings in FastAPI Request Handlers

**What:** Calling the bge-m3 embedding model synchronously inside a FastAPI endpoint handler.

**Why bad:** bge-m3 embedding is CPU-bound (0.5-2 seconds per batch). Running it in the async event loop blocks all concurrent requests. Under load, the entire API becomes unresponsive.

**Instead:** Always run embedding in Celery workers (`indexer.embed_fact()` task). The FastAPI handler writes the fact to the database and enqueues an async Celery task for embedding.

---

### Anti-Pattern 6: Logging Credential Values

**What:** Including `access_token`, `refresh_token`, `password`, or any credential value in log output.

**Why bad:** Audit log files are Loki-ready and will be shipped to a centralized logging system. Credential values in logs create a credential leakage vector accessible to anyone with log access.

**Instead:** Log `user_id`, `tool`, `allowed`, `duration_ms` -- never credential values. Implement CI lint rules to detect credential keywords in log calls.

---

## Scalability Considerations

| Concern | At 100 users (MVP) | At 10K users | At 1M users |
|---------|---------------------|--------------|-------------|
| **Database** | Single PostgreSQL instance | Read replicas + PgBouncer | Sharded PostgreSQL or managed service |
| **Vector search** | pgvector IVFFlat, single instance | Tune IVFFlat lists, consider HNSW | Dedicated vector DB (Qdrant/Weaviate) |
| **LLM calls** | Single LiteLLM proxy | 2-3 LiteLLM replicas behind load balancer | Multiple proxy clusters, request queuing |
| **Agent workers** | Single FastAPI instance | Horizontal FastAPI replicas + Celery scale | Kubernetes HPA, dedicated agent pools |
| **Memory isolation** | SQL `WHERE user_id = $1` | Same pattern, add connection pooling | Tenant-level database partitioning |
| **Channel gateways** | In-process adapters | Separate sidecar services | Dedicated gateway service mesh |
| **Embedding** | 1-2 Celery workers (CPU) | GPU workers, batch processing | Dedicated embedding service cluster |
| **Deployment** | Docker Compose | Kubernetes (single cluster) | Multi-region Kubernetes |

**MVP guidance:** Design for 100 users means Docker Compose, single PostgreSQL, single LiteLLM proxy, 1-2 Celery workers. Do NOT add connection pooling, read replicas, Kubernetes, or dedicated vector DBs until the system demonstrates it needs them.

---

## Build Order (Dependency-Driven)

The architecture has clear dependency chains that dictate build order. Components further down the chain cannot function without the components above them.

```
Phase 1: Identity & Skeleton
  [PostgreSQL + Redis + Keycloak]           -- Infrastructure foundation
  [core/config.py + core/db.py]             -- Config and DB access
  [security/jwt.py + security/rbac.py]      -- Gates 1 and 2
  [gateway/runtime.py]                      -- AG-UI runtime shell
  [frontend/ skeleton]                      -- Next.js + CopilotKit provider
    |
    v
Phase 2: Agents, Tools & Memory
  [gateway/tool_registry.py]                -- Central tool catalog (required before any tool call)
  [tools/*_tools.py]                        -- Backend tool implementations
  [memory/ subsystem]                       -- 3-tier memory with embedding pipeline
  [agents/master_agent.py]                  -- Master agent with LLM calls
  [agents/subagents/*]                      -- Sub-agents (email, calendar, project)
  [LiteLLM proxy + Ollama config]           -- LLM access (required by agents)
    |
    v
Phase 3: Canvas & Workflows                Phase 4: Scheduler & Channels
  [React Flow canvas UI]                     [scheduler/celery_app.py]
  [agents/graphs.py compiler]                [channels/dispatcher.py + adapters]
  [HITL nodes + A2UI widgets]                [Telegram gateway (first channel)]
  [Workflow CRUD API]                        [Channel identity resolution]
  [PostgreSQL checkpointer]
    |                                           |
    v                                           v
Phase 5: Hardening & Sandboxing
  [sandbox/ Docker execution]               -- Untrusted code isolation
  [gateway/agui_middleware.py Gate 3]        -- Tool ACL enforcement
  [credentials/ AES-256 encryption]         -- Credential management
  [MCP ACL integration]                     -- MCP security
  [WhatsApp + Teams adapters]               -- Additional channels
  [Audit logging finalization]              -- structlog JSON
    |
    v
Phase 6: Observability
  [Grafana + Prometheus + Loki + Alloy]     -- Monitoring stack
  [Performance tuning + load testing]       -- Optimization
```

**Key dependency observations:**

1. **Security before everything:** JWT/RBAC (Phase 1) must exist before any agent or tool can execute. This is non-negotiable -- it is the foundation that all other layers build upon.

2. **Tool registry before agents:** The tool registry defines what agents CAN do. Agents without tools are useless. Build the registry and tool implementations before building agents.

3. **Memory before agents:** Agents need memory context (recent turns + relevant facts) to function well. The memory subsystem should be built alongside or before agent orchestration.

4. **Phase 3 and 4 are parallel:** Canvas/Workflows and Scheduler/Channels have no mutual dependencies. Both depend on Phase 2 (agents + tools + memory). They can be built concurrently by separate teams or in either order.

5. **Hardening depends on everything:** Security hardening (Gate 3 ACL, sandbox, credential management) makes sense only after the core features exist. It is the "tighten the bolts" phase.

6. **Observability is last:** You cannot meaningfully monitor a system that does not yet exist. Build observability after the system is functional.

---

## V1.3 Integration: New Feature Architectures

*Added 2026-03-05. Addresses the five specific architectural questions for v1.3.*
*All findings are HIGH or MEDIUM confidence, verified against existing codebase and official docs.*

---

### V1.3-1: Embedding Sidecar Service

#### Current State

bge-m3 embedding runs inside the `celery-worker` Docker container (same image as `backend`).
The `BGE_M3Provider` loads `BAAI/bge-m3` via `FlagEmbedding` — CPU-bound, cached at class
level per worker process. No HTTP boundary exists between task queue and embedding.

#### Architecture

```
blitz-net (Docker)

  celery-worker  --POST /embed--> embedding-sidecar:8010
                 <--JSON vectors--  (FastAPI + bge-m3)

  backend        --POST /embed--> embedding-sidecar:8010  (future real-time path)
```

The sidecar is a standalone FastAPI service in a new `embedding-sidecar/` directory
at the project root. It owns the bge-m3 model and the `transformers<5.0` pin.

#### API Contract

```
POST /embed
  Request:  {"texts": ["string"], "model": "bge-m3"}
  Response: {"vectors": [[float, ...]], "dimension": 1024, "model": "bge-m3"}

GET /health   -> 200 immediately (liveness — process is alive)
GET /ready    -> 200 when model loaded, 503 during startup (readiness gate)
```

Key: `/ready` returns 503 until bge-m3 finishes loading (~30-60s on cold start).
Docker Compose uses `/ready` for the health check so `celery-worker` waits for the
model to be fully initialized before processing tasks.

#### Docker Compose Health Check Pattern

```yaml
embedding-sidecar:
  build: ./embedding-sidecar
  healthcheck:
    test: ["CMD-SHELL", "curl -f http://localhost:8010/ready || exit 1"]
    interval: 30s
    timeout: 10s
    retries: 10
    start_period: 60s     # bge-m3 cold start grace period

celery-worker:
  depends_on:
    embedding-sidecar:
      condition: service_healthy   # worker waits for model ready
```

`start_period: 60s` is critical — without it Docker marks the container unhealthy
before the model loads and enters a restart loop.

#### Component Impact

**New:** `embedding-sidecar/` (Dockerfile, main.py, requirements.txt)

**New class in** `backend/memory/embeddings.py`:
```python
class RemoteEmbeddingProvider:
    dimension: int = 1024
    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self._base_url}/embed", json={"texts": texts})
            resp.raise_for_status()
            data = resp.json()
            assert data["dimension"] == self.dimension
            return data["vectors"]
```

**Modified:** `backend/core/config.py` — add `embedding_sidecar_url: str = "http://embedding-sidecar:8010"`

**Modified:** `backend/scheduler/tasks/embedding.py` — replace `BGE_M3Provider()` with `RemoteEmbeddingProvider(settings.embedding_sidecar_url)`

**Unchanged:** pgvector dimension (1024), Celery task signatures, `embed_and_store`/`summarize_episode` interfaces

**Confidence:** MEDIUM — pattern is straightforward. The `start_period` duration for bge-m3 requires validation on target hardware.

---

### V1.3-2: Next.js Route Group Layout for Navigation Rail

#### Current State

No global navigation. Each page (`/chat`, `/admin`, `/workflows`, `/settings`) is standalone.
Root `layout.tsx` contains only `SessionProvider`. Pages each handle their own auth redirect.

#### Pattern: Route Groups

Next.js 15 App Router route groups use `(group-name)` folders — parentheses are stripped
from URLs so routes do not change. A shared `layout.tsx` inside the group applies to all
routes within it without affecting URL paths.

```
app/
├── layout.tsx                     # root: SessionProvider only (unchanged)
├── login/                         # outside group — no nav
├── (app)/                         # route group — shared nav rail
│   ├── layout.tsx                 # NEW: auth check + NavRail + <main>{children}</main>
│   ├── chat/page.tsx              # /chat — gets nav rail, URL unchanged
│   ├── workflows/                 # /workflows — gets nav rail, URL unchanged
│   ├── skills/page.tsx            # /skills — NEW catalog page
│   ├── profile/page.tsx           # /profile — NEW
│   └── settings/page.tsx         # /settings — URL unchanged
├── admin/                         # OUTSIDE (app) group — admin layout unchanged
│   ├── layout.tsx                 # admin-specific layout with role check
│   └── ...
```

The `(app)/layout.tsx` is a Server Component that:
1. Calls `auth()` and redirects to `/login` if no session (removes duplicate auth checks from each page)
2. Renders `<NavRail session={session} />` as a Client Component (needs `usePathname()`)
3. Renders `<main className="flex-1">{children}</main>` for page content

```typescript
// frontend/src/app/(app)/layout.tsx
export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session) redirect("/login");
  return (
    <div className="flex h-screen">
      <NavRail session={session} />
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}
```

#### Migration Impact

Pages moved from `app/X/` to `app/(app)/X/` — URLs unchanged.
Existing pages that call `const session = await auth(); if (!session) redirect("/login")` can remove that boilerplate.
`ChatLayout` component needs CSS update: use remaining width after nav rail, not full viewport.

`admin/` stays outside `(app)/`. Admin layout handles its own auth and role check independently.
The nav rail can include an "Admin" link pointing to `/admin` (full page reload across layout boundary is acceptable).

**Confidence:** HIGH — Next.js 15 route groups are the canonical documented pattern for this exact use case. URL paths are confirmed unaffected by the group folder name.

---

### V1.3-3: Skill Catalog with PostgreSQL tsvector

#### Current State

`skill_definitions` table has `name`, `description`, `instruction_markdown` columns but no
search index. List endpoint returns all active skills with Python-level permission filtering.
At 20 skills: acceptable. At 100-500 skills (marketplace): `LIKE '%q%'` becomes slow.

#### Migration: Generated tsvector Column

```sql
-- Alembic migration 020
ALTER TABLE skill_definitions
    ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(name, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(display_name, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(description, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(slash_command, '')), 'C') ||
        setweight(to_tsvector('english', coalesce(instruction_markdown, '')), 'D')
    ) STORED;

CREATE INDEX ix_skill_definitions_search_vector
    ON skill_definitions USING GIN (search_vector);
```

`GENERATED ALWAYS AS ... STORED` means PostgreSQL maintains the vector automatically on
INSERT/UPDATE — zero application code changes for writes. GIN index enables fast `@@` queries.

Weight rationale: name/display_name rank highest (A) because users search by skill name;
description is context (B); slash_command is a secondary identifier (C); instruction body
is full-text content (D). This matches user expectation of relevance.

SQLite test compatibility: `GENERATED ALWAYS AS ... STORED` is PostgreSQL-only. The migration
must be guarded. Tests that exercise `?q=` search should be marked to skip on SQLite
(consistent with the existing `MemoryFact` isolation pattern).

#### Search API Design

```python
# Modified: GET /api/skills
@router.get("")
async def list_user_skills(
    q: str | None = Query(None),
    skill_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ...
) -> list[SkillListItem]:
    stmt = select(SkillDefinition).where(
        SkillDefinition.status == "active",
        SkillDefinition.is_active == True,
    )
    if q:
        stmt = stmt.where(
            SkillDefinition.search_vector.op("@@")(
                func.plainto_tsquery("english", q)
            )
        ).order_by(
            func.ts_rank(SkillDefinition.search_vector,
                         func.plainto_tsquery("english", q)).desc()
        )
    else:
        stmt = stmt.order_by(SkillDefinition.name)
    ...
```

`plainto_tsquery` (not `to_tsquery`) handles raw user input without syntax errors.
`ts_rank` ordering surfaces skills where query matches name/description ahead of body matches.
`?q=` is optional — no query returns all visible skills (existing behavior preserved).
Pagination (`limit`/`offset`) added because catalog grows with marketplace.

Same `?q=` pattern applies to `GET /api/admin/skills`.

**Confidence:** HIGH — PostgreSQL tsvector/tsquery/GIN index pattern is well-documented. `GENERATED ALWAYS AS STORED` is the standard approach for auto-maintained search vectors.

---

### V1.3-4: Keycloak as Optional Runtime Configuration

#### Current State

All Keycloak connection details are environment-variable-only (`backend/.env`), read at startup
by `Settings` (pydantic-settings). If Keycloak is unreachable, the first RS256 token validation
fails with HTTP 503 but the backend starts normally (local auth still works).

v1.3 goal: Keycloak becomes configurable from the admin UI without container restart, with
local auth as the always-available fallback.

#### Config Resolution Pattern

```
JWT validation (security/jwt.py)
    |
    iss == "blitz-local" ─────────────────> local HS256 path (no Keycloak needed)
    |
    iss == keycloak_issuer
        |
        get_keycloak_config()             <-- NEW function
            |
            ┌─ DB: system_config table ───────────────────────────────────────┐
            │   key: "keycloak.url"      value: {"value": "https://..."}     │
            │   key: "keycloak.realm"    value: {"value": "blitz-internal"}  │
            │   key: "keycloak.enabled"  value: {"value": true}              │
            └─────────────────────────────────────────────────────────────────┘
                |  (miss or key absent)
                v
            env vars via Settings (KEYCLOAK_URL, KEYCLOAK_REALM, etc.)
```

The `system_config` table already exists (introduced in v1.1). Keycloak config keys are
added to it by the admin UI. A new `backend/core/keycloak_config.py` module implements
`get_keycloak_config()` with a 60-second in-process cache (same TTL as JWKS cache).
`invalidate_keycloak_config()` is called by the admin UI after saving, forcing immediate
re-read.

Secrets (`client_secret`, `admin_password`) stored in `system_config` must be AES-256
encrypted using the existing `CREDENTIAL_ENCRYPTION_KEY` — NOT as plaintext JSONB.
Same pattern as `user_credentials` table.

#### JWKS Cache Keying Change

Current: JWKS cache is module-level state, implicitly keyed to the startup `settings.keycloak_jwks_url`.
Required: JWKS cache must be keyed by the JWKS URL string to handle admin changes.

```python
# security/jwt.py — modified
_JWKS_CACHE: dict[str, dict] = {}  # keyed by jwks_url, not a single dict

async def _get_jwks(jwks_url: str) -> dict:
    if jwks_url in _JWKS_CACHE and (now - _fetched_at[jwks_url]) < JWKS_TTL_SECONDS:
        return _JWKS_CACHE[jwks_url]
    jwks = await _fetch_jwks_from_remote(jwks_url)
    _JWKS_CACHE[jwks_url] = jwks
    _fetched_at[jwks_url] = now
    return jwks
```

#### New Admin Endpoints

```
GET  /api/admin/config/keycloak       — read current Keycloak config (masked secrets)
PUT  /api/admin/config/keycloak       — save to system_config + invalidate_keycloak_config()
POST /api/admin/config/keycloak/test  — test connection (fetch JWKS, verify realm accessible)
```

All require `registry:manage` permission (existing admin gate).

#### Boot Sequence

```
Backend starts (always succeeds even if Keycloak unreachable)
    |
Local auth works immediately (HS256, no external dependency)
    |
First Keycloak token:
    get_keycloak_config() -> check DB -> fall back to env
    fetch JWKS (fails gracefully with 503 if unreachable)
    |
Admin configures Keycloak via UI:
    saves to system_config -> invalidate_keycloak_config()
    next Keycloak token uses new config within 60 seconds
```

New installations: boot with local auth only, admin creates first admin account
via local credentials, then configures Keycloak from the UI.

**Confidence:** MEDIUM — `system_config` table is the correct extension point. The JWKS
cache keying change requires care to avoid stale entries. Touches Gate 1 (highest risk area).

---

### V1.3-5: Security Review Node in LangGraph Builder Graph

#### Current State

`artifact_builder.py` implements a LangGraph graph for AI-assisted artifact creation
(the admin wizard). The graph takes user instructions, calls an LLM to generate artifact
definitions (including `procedure_json` for skills), and returns them without a security
gate. The existing `SecurityScanner` in `skills/security_scanner.py` runs only on
externally imported skills — not on AI-generated ones.

#### New Graph Topology

```
START
  |
intent_classification
  |
form_extraction
  |
artifact_generation
  |
  [if skill_type == "procedural"]
  |
security_review_node          <-- NEW
  |
  +--[score >= 70]--> finalize_node --> END (status="active")
  |
  +--[score < 70, retry < 3]--> refine_with_feedback --> artifact_generation (retry)
  |
  +--[score < 70, retry >= 3]--> quarantine_node --> END (status="quarantine")
```

Non-skill artifacts (agents, tools, MCP servers) bypass the security review node.
The conditional edge routes to quarantine after 3 failed retries, not an infinite loop.

#### Implementation

```python
# backend/agents/builder_nodes.py — new node

SECURITY_PASS_THRESHOLD = 70   # same as import pipeline threshold

async def security_review_node(state: BuilderState) -> dict:
    procedure_json = state.get("generated_artifact", {}).get("procedure_json")
    if procedure_json is None:
        return {"security_passed": True, "security_score": 100}

    scanner = SecurityScanner()
    report = scanner.scan_dict(procedure_json)
    retry_count = state.get("security_retry_count", 0)

    return {
        "security_score": report["score"],
        "security_report": report,
        "security_passed": report["score"] >= SECURITY_PASS_THRESHOLD,
        "security_retry_count": retry_count + 1,
    }

def route_security_result(state: BuilderState) -> str:
    if state.get("security_passed"):
        return "finalize"
    if state.get("security_retry_count", 0) >= 3:
        return "quarantine"
    return "refine_with_feedback"
```

#### BuilderState Extensions

```python
# backend/agents/builder_state.py
class BuilderState(TypedDict):
    # ... existing fields ...
    security_score: int | None
    security_report: dict | None
    security_passed: bool | None
    security_retry_count: int
    quarantined: bool
```

#### Quarantine Integration

When `quarantined = True`, the artifact is saved with `status="quarantine"` — entering
the same admin review queue as externally imported skills (`GET /api/admin/skills/pending`).
No new admin workflow required; the existing review/approve/reject pipeline handles it.

**Confidence:** HIGH — LangGraph conditional edges and retry loops are established patterns.
Integration reuses existing `SecurityScanner` and quarantine pipeline without new infrastructure.

---

### V1.3 Component Map: New vs Modified

```
NEW COMPONENTS                          MODIFIED COMPONENTS

embedding-sidecar/                      backend/memory/embeddings.py
  Dockerfile                              + RemoteEmbeddingProvider class
  main.py (FastAPI + bge-m3)            backend/core/config.py
  requirements.txt                        + embedding_sidecar_url setting

backend/core/keycloak_config.py         backend/scheduler/tasks/embedding.py
  get_keycloak_config()                   replace BGE_M3Provider with Remote
  invalidate_keycloak_config()

frontend/src/app/(app)/                 backend/security/jwt.py
  layout.tsx (auth + NavRail)             JWKS cache keyed by URL
                                          uses get_keycloak_config() at runtime
frontend/src/components/nav/
  nav-rail.tsx (Client Component)       backend/core/models/skill_definition.py
  nav-rail-item.tsx                       + search_vector tsvector GENERATED column

backend/alembic/versions/020_*.py       backend/api/routes/user_skills.py
  tsvector column + GIN index             + ?q= search, limit/offset pagination

backend/api/routes/admin_keycloak.py    backend/api/routes/admin_skills.py
  GET/PUT/POST keycloak config            + ?q= search param

backend/agents/builder_nodes.py         backend/agents/artifact_builder.py
  security_review_node                    + security gate branch for skills
  refine_with_feedback_node
  quarantine_node                       docker-compose.yml
  finalize_node                           + embedding-sidecar service
                                          celery-worker depends_on sidecar

                                        frontend app pages (chat, workflows, settings)
                                          moved to (app)/ group, auth boilerplate removed
```

---

### V1.3 Recommended Build Order

```
1. (app) route group layout          [frontend only, zero backend deps]
   + NavRail component
   + Profile page skeleton
   Unblocks: /skills catalog page, nav-aware CSS on ChatLayout

2. Embedding sidecar                 [infrastructure, no code dependencies]
   + Docker Compose service
   + RemoteEmbeddingProvider
   + Celery task update
   Can run in parallel with item 1.

3. tsvector skill catalog            [DB migration + API extension]
   + Migration 020
   + ?q= on /api/skills and /api/admin/skills
   + /skills frontend catalog page (requires item 1 nav rail)
   Requires item 1 to expose the UI.

4. Security review node              [LangGraph builder graph change]
   + security_review_node
   + BuilderState extensions
   + Quarantine integration test
   Independent of items 1-3. Can be done in parallel with items 1-2.

5. Keycloak runtime config           [auth path change — highest risk]
   + keycloak_config.py
   + JWKS cache re-keying
   + Admin UI config endpoints
   Last because it touches Gate 1. Requires item 1 (admin UI exists for config screen).
```

Parallelization: Items 1+2+4 can be built concurrently. Items 3 and 5 depend on item 1 UI.
Item 5 should be last due to Gate 1 risk (JWT validation is on every request).

---

## Sources

- [Blitz AgentOS Architecture Document](docs/architecture/architecture.md) -- PRIMARY source (HIGH confidence)
- [Blitz AgentOS Blueprint](docs/design/blueprint.md) -- Design decisions (HIGH confidence)
- [Blitz AgentOS Module Breakdown](docs/design/module-breakdown.md) -- Directory structure (HIGH confidence)
- [Blitz AgentOS Memory Subsystem](docs/design/memory-sub-system.md) -- Memory design (HIGH confidence)
- [Blitz AgentOS Channel Integration](docs/design/channel-integration.md) -- Channel patterns (HIGH confidence)
- [Blitz AgentOS Backend Capabilities](docs/design/backend-capabilities.md) -- Agent/tool/workflow patterns (HIGH confidence)
- [Blitz AgentOS Implementation Guide](docs/implementation/implementation-guide.md) -- Phase structure (HIGH confidence)
- [Salesforce Enterprise Agentic Architecture](https://architect.salesforce.com/fundamentals/enterprise-agentic-architecture) -- Enterprise patterns (MEDIUM confidence)
- [LangGraph Multi-Agent Orchestration Guide](https://latenode.com/blog/ai-frameworks-technical-infrastructure/langgraph-multi-agent-orchestration/langgraph-multi-agent-orchestration-complete-architecture-guide-multi-agent-orchestration-analysis) -- LangGraph patterns (MEDIUM confidence)
- [LangChain Durable Execution Docs](https://docs.langchain.com/oss/python/langgraph/durable-execution) -- PostgresSaver pattern (HIGH confidence)
- [CopilotKit AG-UI + LangGraph Integration](https://www.copilotkit.ai/blog/how-to-add-a-frontend-to-any-langgraph-agent-using-ag-ui-protocol) -- AG-UI protocol (MEDIUM confidence)
- [MCP Specification](https://modelcontextprotocol.io/specification/2025-11-25) -- MCP protocol (HIGH confidence)
- [React Flow v12 Documentation](https://reactflow.dev/) -- Canvas library (HIGH confidence)
- [Next.js 15 Route Groups](https://nextjs.org/docs/app/api-reference/file-conventions/route-groups) -- Frontend nav pattern (HIGH confidence)
- [Next.js Layouts and Pages](https://nextjs.org/docs/app/getting-started/layouts-and-pages) -- Layout nesting (HIGH confidence)
- [PostgreSQL Full-Text Search Documentation](https://www.postgresql.org/docs/current/textsearch-controls.html) -- tsvector/tsquery (HIGH confidence)
- [PostgreSQL Text Search Types](https://www.postgresql.org/docs/current/datatype-textsearch.html) -- GENERATED STORED tsvector (HIGH confidence)
- [FastAPI Full-Text Search with PostgreSQL](https://www.slingacademy.com/article/how-to-use-postgresql-full-text-search-in-fastapi-applications/) -- Integration pattern (MEDIUM confidence)
- [Agent Skills Specification](https://agentskills.io/specification) -- Skill format standard (HIGH confidence)
- [LangGraph Best Practices 2025](https://www.swarnendu.de/blog/langgraph-best-practices/) -- Graph patterns (MEDIUM confidence)
- [FastAPI Docker Health Checks](https://betterstack.com/community/guides/scaling-python/fastapi-docker-best-practices/) -- Sidecar health pattern (MEDIUM confidence)
