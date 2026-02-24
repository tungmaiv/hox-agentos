
# Blitz AgentOS – Solution Blueprint (MVP, On‑Premise, Enterprise)

This blueprint describes the end‑to‑end architecture for Blitz AgentOS: an enterprise, on‑premise, OpenClaw‑style agentic platform built with Next.js, CopilotKit (AG‑UI, A2UI), FastAPI, LangGraph, PydanticAI, Keycloak, PostgreSQL, Redis, and Docker.[file:18]

---

## 1. Business Goals & Scope

### 1.1 Goals

- Provide Blitz employees (~100 users) with a unified **Agentic Operating System** to:
  - Automate daily workflows (morning email/calendar digest, project summaries, reminders).  
  - Orchestrate multi‑step business processes via a low‑code canvas.  
  - Connect to internal systems via MCP (CRM, project tools, data warehouse).  
  - Interact via web UI and external channels (Telegram/WhatsApp/Slack).[file:18]

- Enforce enterprise‑grade **security**, with:
  - Single Sign‑On via Keycloak (OIDC/JWT).  
  - RBAC and fine‑grained ACL per tool and MCP function.[file:18][file:7]  
  - Per‑user hierarchical memory isolation.[file:15]  
  - Docker sandboxing for untrusted code execution.[file:14]

### 1.2 MVP Capabilities

- Low‑code workflow studio (canvas).  
- Deep master agent orchestration via LangGraph.  
- Hierarchical memory (short/medium/long term).  
- Autonomous job scheduler (cron‑like).  
- Web chat with AG‑UI + A2UI generative UI.  
- At least one external channel (Telegram or Slack).  
- MCP integration to at least one Blitz system (e.g., CRM).[file:18]

---

## 2. High‑Level Architecture

Blitz AgentOS uses a **three‑tier model**.[file:18]

### 2.1 Tiers

1. **Agentic Frontend (Next.js + CopilotKit)**  
   - AG‑UI client for real‑time chat and tool streaming.  
   - A2UI renderer for LLM‑driven widgets (cards, forms, tables).  
   - Low‑code canvas to define workflows visually.[file:18]

2. **Security Runtime (FastAPI Copilot Runtime + Keycloak)**  
   - Single entry point for all AG‑UI, tools, and MCP calls.  
   - Validates Keycloak JWTs, enforces RBAC and ACL.  
   - Registers tools and MCP servers; acts as security proxy.[file:18][file:7]

3. **Backend Orchestrator (LangGraph + PydanticAI)**  
   - Master deep agent with planning and sub‑agent spawning.  
   - LangGraph StateGraphs compiled from canvas workflows.  
   - Pydantic models for tool I/O, memory, and workflow structures.[file:18]

### 2.2 Core Services

- `frontend/` – Next.js + CopilotKit app.  
- `backend/` – FastAPI runtime + LangGraph, scheduler, MCP, memory.  
- `keycloak/` – Identity & Access Management.  
- `postgres/` – Primary data store.  
- `redis/` – Scheduler queue, caching.  
- `sandbox-runtime/` – Docker environment for sandbox tools.  
- `channel-gateways/` – Optional external channel connectors.

---

## 3. Backend Architecture (FastAPI + LangGraph)

### 3.1 Backend Directory Layout

Aligned with the multi‑layer structure for agents, tools, gateway, security, and memory.[file:1][file:18]

```text
backend/
  main.py
  api/
    routes/
      auth.py
      agents.py
      workflows.py
      scheduler.py
      channels.py
      mcp.py
  core/
    config.py
    db.py
    logging.py
    models/
      user.py
      acl.py
      workflow.py
      job.py
      memory.py
      channel.py
      mcp.py
    schemas/
      auth.py
      common.py
      workflow.py
      job.py
      agent.py
      memory.py
      channel.py
  security/
    keycloak_client.py
    jwt.py
    rbac.py
    acl.py
    deps.py
  gateway/
    runtime.py
    agui_middleware.py
    tool_registry.py
  agents/
    master_agent.py
    graphs.py
    state/
      types.py
    subagents/
      email_agent.py
      calendar_agent.py
      project_agent.py
      channel_agent.py
  tools/
    email_tools.py
    calendar_tools.py
    project_tools.py
    dataops_tools.py
    sandbox_tools.py
  sandbox/
    docker_client.py
    policies.py
    executor.py
  mcp/
    client.py
    servers/
      crm_server.py
  scheduler/
    celery_app.py
    worker.py
    jobs.py
  memory/
    short_term.py
    medium_term.py
    long_term.py
    summarizer.py
  channels/
    dispatcher.py
    models.py
```


### 3.2 Core \& DB

`core/config.py`: Pydantic settings for DB URLs, Redis, Keycloak realm/client, sandbox limits, MCP endpoints.[file:1]

`core/db.py`: SQLAlchemy session and Base definition.

---

## 4. Security, RBAC, and ACL

### 4.1 Authentication Flow

1. User logs in via Keycloak (OIDC) and receives JWT.
2. Frontend attaches JWT to all AG‑UI and REST calls to backend.
3. FastAPI Copilot Runtime validates JWT, extracts user ID and roles.
4. Runtime injects user context into each agent/tool call.[file:11][file:18]

### 4.2 Keycloak Integration

`security/keycloak_client.py`:

- Fetch Keycloak JWKS and cache keys.
- Optionally call introspection endpoint for advanced checks.

`security/jwt.py`:

- Decode and verify JWT (signature, expiry, issuer, audience).
- Returns a `TokenClaims` object.


### 4.3 RBAC and ACL

`security/rbac.py`:

- Maps Keycloak roles to internal `Role` and `Permission` tables.
- Helper: `has_permission(user, "tool:email.read")`.[file:11]

`core/models/acl.py`: defines Role, Permission, RolePermission, UserRole, ToolAcl.[file:1]

`security/acl.py`:

- For each tool or MCP function, checks `ToolAcl` and user roles.[file:7]
- Denies execution for unauthorized calls.

`security/deps.py`:

- FastAPI dependency `get_current_user()`
- `require_permission("tool:...")` decorator for REST endpoints.


### 4.4 AG‑UI Middleware for ACL (MCP \& Tools)

`gateway/agui_middleware.py`:

- Registered via `sdk.agent.use` (CopilotKit SDK) or directly in FastAPI.[file:7]
- On each event:
    - Extracts user from JWT.
    - If event is `TOOLCALL_START`, reads `tool_name`.
    - Invokes `check_permission(user, tool_name)` and `check_acl(user, tool_name)`.
    - If denied, returns 403 via AG‑UI and prevents tool execution.

This centralizes security at the runtime boundary and covers MCP tools as well.[file:7]

---

## 5. Deep Agent Orchestration (LangGraph)

### 5.1 Master Agent

`agents/master_agent.py`:

- Initializes `create_deep_agent(...)` with:
    - Planner (multi‑step planning).
    - File‑system context for per‑run temp data.
    - Tool registry for backend tools \& MCP.
    - Sub‑agent spawning for specialized tasks.[file:18]

Responsibilities:

- `run_conversation(user_context, message, channel)`:
    - Handles chat‑like interactions via AG‑UI.
    - Calls sub‑agents and tools as needed.
- `run_workflow(workflow_id, params, user_context)`:
    - Compiles workflow definition into a `StateGraph`.
    - Executes graph (with optional HITL checkpoints).


### 5.2 Workflow → StateGraph

`agents/graphs.py`:

- `compile_workflow_to_stategraph(workflow: Workflow) -> StateGraph`:
    - Parses `definition_json` (canvas nodes and edges).
    - Maps node types:
        - `agent` → sub‑agent node.
        - `tool` → backend tool node.
        - `mcp` → MCP tool node.
        - `hitl` → human approval (renderAndWait).[file:18][file:17]
    - Wires transitions based on success/failure connectors.

State type is defined in `agents/state/types.py` and is shared across nodes.

### 5.3 Sub‑Agents

`agents/subagents/`:

- `email_agent.py` – summarization, routing of emails.
- `calendar_agent.py` – event listing and agenda summaries.
- `project_agent.py` – task and project workflows.
- `channel_agent.py` – multi‑channel messaging decisions.

Each sub‑agent uses its own tools and may schedule follow‑up jobs.

---

## 6. Backend Tools \& MCP

### 6.1 Backend Tools

`tools/*.py` define Pydantic‑validated tools:

- Example (email):

```python
class FetchEmailsInput(BaseModel):
    user_id: str
    since: datetime

class EmailSummary(BaseModel):
    subject: str
    from_: str
    snippet: str

@tool
def fetch_emails(input: FetchEmailsInput) -> list[EmailSummary]:
    ...
```

- Tools are registered in `gateway/tool_registry.py` with metadata:
    - `name`, `description`, `required_permissions`, `sandbox_required`.[file:1]


### 6.2 Sandbox Tools (Claude‑Code/OpenClaw‑style)

`tools/sandbox_tools.py`:

- `@tool def bash_exec(...)`
- `@tool def python_exec(...)`

These call the sandbox executor rather than running on host.

`sandbox/docker_client.py` and `sandbox/policies.py`:

- Build and run per‑session containers (OpenClaw‑inspired).[file:14]
- Use:
    - Per‑session isolation.
    - Minimal base images (`sandbox-common`, `sandbox-browser`).
    - Least‑privilege (only needed binaries and permissions).[file:14]

`sandbox/executor.py`:

- On call:

1. Check if tool requires sandbox (via registry).
2. Create container with resource limits.
3. Execute command/script.
4. Capture stdout/stderr.
5. Destroy container and return result.[file:14]


### 6.3 MCP Integration

`mcp/client.py`:

- Generic MCP client that:
    - Connects to MCP servers (gRPC/WebSocket/HTTP depending on spec).
    - Discovers tools (list, describe).
    - Executes tools with structured JSON input.[file:18]

`mcp/servers/crm_server.py`:

- Provides standardized MCP tools for CRM:
    - `crm.search_leads`, `crm.get_contact`, etc.

ACL for MCP tools enforced by `ToolAcl` and AG‑UI middleware.[file:7]

---

## 7. Hierarchical Memory (PostgreSQL‑based)

### 7.1 Design Goals

- **Three‑tier memory**: short‑term verbatim, medium‑term summarized, long‑term factual.[file:15]
- **Per‑user isolation**: no cross‑user reads.
- **Context optimization**: only inject relevant summaries and facts into prompts.


### 7.2 Data Model Summary

`core/models/memory.py` defines:

- `ShortTermMemory` – raw recent conversation turns, keyed by `user_id` and `conversation_id`.
- `MediumTermMemory` – summaries of sessions or N turns, with `from_ts`, `to_ts`.
- `LongTermFact` – durable facts and preferences, optionally with embeddings.[file:15]


### 7.3 Access Patterns

`memory/short_term.py`:

- Append new messages per turn.
- Read last N turns for prompt.

`memory/medium_term.py`:

- Periodically (or after threshold) summarize short‑term history into medium‑term.
- Use LLM summarizer; store textual summary.

`memory/long_term.py`:

- CRUD for user facts:
    - `preferred_language`, roles, key business context.
- Optional semantic search using embeddings.

All functions accept a `user_id` and always filter by it; RBAC can further restrict which facts agents can see per role.[file:15]

---

## 8. Scheduler \& Job Orchestration

### 8.1 Components

- `scheduler/celery_app.py` – Celery config with Redis broker.
- `scheduler/jobs.py` – job scheduling logic (cron parsing, next run computation).[file:18]
- `scheduler/worker.py` – Celery worker code executing LangGraph workflows.


### 8.2 Job Model

`core/models/job.py`:

- `ScheduledJob` with:
    - `user_id`, `workflow_id`, `name`, `schedule_cron`, `timezone`, `enabled`, `params`, `delivery_channel`.


### 8.3 Execution Flow

1. Admin or user creates/edit job via `/api/scheduler/jobs`.
2. Celery beat or a custom scheduler enqueues `run_scheduled_job(job_id)` at the right time.
3. Worker:
    - Loads job and user; builds user context (incl. roles).
    - Loads workflow definition and compiles to StateGraph.
    - Runs via `master_agent.run_workflow`.
    - Persists `WorkflowRun` and updates `last_run_at`/`next_run_at`.
    - Uses `channels.dispatcher.send_message` or A2UI notification to deliver results.[file:18]

This powers morning email/calendar summaries, daily project digests, and other automations.

---

## 9. Channels \& Multi‑Channel UX

### 9.1 Data Model

`core/models/channel.py`:

- `ChannelAccount`: maps Blitz user to external account (e.g., Telegram user ID).
- `ChannelSession`: maps channel account to AG‑UI `conversation_id` and last activity.


### 9.2 Backend Channel Dispatcher

`channels/dispatcher.py`:

- `send_message(user_id, channel, payload)`:
    - Resolves `ChannelAccount`.
    - Calls channel‑specific adapter (telegram, slack, etc.) or returns to web UI.


### 9.3 External Gateways

Optional `channel-gateways/telegram` microservice:

- Receives Telegram webhooks.
- Resolves to `User` using `ChannelAccount`.
- Calls `backend/api/channels.py` endpoint:
    - Passes message text and metadata.
    - Backend processes via `master_agent.run_conversation`.
    - Returns a response which is sent back to Telegram.

Security:

- Gateways authenticate to backend via service account + JWT or HMAC.
- Backend still enforces per‑user ACL for all tools.

---

## 10. Frontend Architecture (Next.js + CopilotKit + A2UI)

### 10.1 Directory Layout

```text
frontend/
  src/
    app/
      layout.tsx
      page.tsx
      api/
        copilotkit/route.ts
    components/
      canvas/
        CanvasRoot.tsx
        NodePalette.tsx
        NodeRenderer.tsx
      chat/
        ChatPanel.tsx
        MessageList.tsx
        InputBar.tsx
      a2ui/
        A2UIMessageRenderer.tsx
        widgets/
          Card.tsx
          Table.tsx
          Form.tsx
          Progress.tsx
    hooks/
      use-copilot-provider.ts
      use-frontend-tools.ts
      use-acl.ts
      use-co-agent.ts
    lib/
      types.ts
      a2ui-spec.ts
    styles/
      globals.css
      tailwind.config.ts
```


### 10.2 Copilot Provider \& Auth

`hooks/use-copilot-provider.ts`:

- Wraps the app with CopilotKit provider and Keycloak session.
- Ensures JWT is injected into AG‑UI headers.[file:11]

`app/api/copilotkit/route.ts`:

- Next.js route that proxies AG‑UI traffic to FastAPI Copilot Runtime.


### 10.3 Low‑Code Canvas

`components/canvas/CanvasRoot.tsx`:

- Renders workflow nodes/edges and binds user actions.

`hooks/use-co-agent.ts`:

- Uses `useCoAgent` to keep canvas state in sync with backend StateGraph:
    - When user edits the canvas, updates are sent to backend.
    - When agent modifies the workflow (e.g., suggestions), frontend updates automatically.[file:17]

`hooks/use-frontend-tools.ts`:

- Registers tools for canvas manipulation via `useFrontendTool`:
    - `addNode`, `updateNode`, `deleteNode`, etc.[file:17]

Workflow definitions are saved as JSON and stored in `Workflow.definition_json`.[file:18]

### 10.4 Chat + A2UI

`components/chat/ChatPanel.tsx`:

- Standard chat interface; AG‑UI handles streaming tokens and tool calls.

`components/a2ui/A2UIMessageRenderer.tsx`:

- Parses A2UI JSONL envelopes (`surfaceUpdate`, `dataModelUpdate`) and renders them as React components.[file:13]
- Supports:
    - Summary cards
    - Forms (e.g., approval dialogs)
    - Tables and progress indicators

Agents are instructed (via system prompt) to emit A2UI specs when presenting structured data or requiring user input.[file:18]

---

## 11. Implementation Phases

### Phase 1 – Identity \& Skeleton

- Deploy Keycloak, Postgres, Redis.
- Implement FastAPI runtime with JWT middleware and simple `agents/chat` endpoint.
- Set up Next.js with CopilotKit provider and AG‑UI chat.


### Phase 2 – Agents, Tools, and Memory

- Implement master agent and basic sub‑agents (email, calendar, project).
- Implement backend tools and Pydantic schemas.
- Implement hierarchical memory (short + medium + long term) with per‑user isolation.[file:15]


### Phase 3 – Canvas \& Workflows

- Implement low‑code canvas and persist `Workflow.definition_json`.
- Implement `compile_workflow_to_stategraph` to run visual workflows.[file:17][file:18]
- Add HITL nodes via A2UI + `renderAndWait` semantics.


### Phase 4 – Scheduler \& Channels

- Implement Celery‑based scheduler and job REST APIs.
- Implement at least one external channel (e.g., Telegram gateway).
- Wire scheduler outputs to web and channels.


### Phase 5 – Hardening \& Sandboxing

- Implement Docker sandbox for unsafe tools and enforce allowlist/denylist.[file:14]
- Add ACL middleware for MCP tools and refine role/permission model.[file:7]
- Add audit logging to track all tool invocations per user.

---

## 12. Non‑Functional Considerations

- **On‑Premise Deployment**: Use Docker Compose initially; later scale to Kubernetes for HA and auto‑scaling.
- **Observability**: Structured logs, metrics for tool usage, job success/failures.
- **Performance**: Warm LLM and sandbox containers, caching, and context summarization to keep latency acceptable.[file:14][file:15]
- **Data Protection**: Encrypt volumes, restrict DB access, log access to sensitive tools.

---

This blueprint provides the architecture, module structure, and data model foundations for Blitz AgentOS so your architecture and dev teams can begin detailed design and implementation discussions.


