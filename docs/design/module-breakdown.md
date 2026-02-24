<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>


# Blitz AgentOS – MVP Architecture & Module Breakdown

Target: Enterprise, on‑premise, OpenClaw‑style agentic platform for Blitz (~100 employees) with authentication, RBAC/ACL, scheduling, channel integrations, MCP, and low‑code workflows using:
- Frontend: Next.js + CopilotKit (AG‑UI, A2UI)
- Backend: FastAPI + LangGraph Deep Agents + PydanticAI
- Security: Keycloak (OIDC/JWT)
- Infra: PostgreSQL, Redis, Docker (sandbox), optional vector DB

This document is meant as a working spec for architects and devs to start design discussions and implementation.

---

## 1. High‑Level Services

### 1.1 Service List

- `frontend/` – Next.js + CopilotKit agentic UI  
- `backend/` – FastAPI Copilot Runtime + LangGraph orchestrator  
- `keycloak/` – Identity provider (realm, clients, roles)  
- `postgres/` – Primary relational DB (users, ACL, workflows, jobs, memory)  
- `redis/` – Scheduler queue, short‑lived caching  
- `sandbox-runtime/` – Docker runtime for unsafe backend tools (code, shell)  
- `channel-gateways/` – Optional microservices for Telegram/WhatsApp/Slack

---

## 2. Project Root Layout

Root layout aligned with the “Enterprise Agentic App Folder Structure”.[file:1][file:18]

```text
blitz-agentos/
  docker-compose.yml
  .env
  backend/
  frontend/
  infra/
    keycloak/
    postgres/
    redis/
    sandbox-runtime/
  docs/
    architecture/
```

- `docker-compose.yml`: Dev orchestration for FastAPI, Next.js, Postgres, Redis, Keycloak, sandbox.
- `.env`: Shared secrets (DB URL, Redis URL, Keycloak URLs, MCP endpoints).

---

## 3. Backend Structure (FastAPI + LangGraph)

Backend is the **central nervous system**: Copilot Runtime, security gateway, scheduler, agents, tools, MCP, and memory.[file:1][file:18]

```text
backend/
  main.py
  api/
    __init__.py
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
      __init__.py
      types.py
    subagents/
      email_agent.py
      calendar_agent.py
      project_agent.py
      channel_agent.py
  tools/
    __init__.py
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
      docs_server.py
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
    telegram_adapter.py   # optional
    whatsapp_adapter.py   # optional
    slack_adapter.py      # optional
```


### 3.1 `core/config.py`

Central configuration (Pydantic settings):

- DB connection strings
- Redis URL
- Keycloak realm, client, public key URL
- Sandbox limits (CPU, memory, timeout)
- MCP endpoints


### 3.2 `core/db.py`

SQLAlchemy (or SQLModel) session factory for PostgreSQL.[file:18]

- `SessionLocal` for API requests
- Base model metadata

---

## 4. Backend Data Models (PostgreSQL)

Representative SQLAlchemy/SQLModel style models.[file:1][file:15][file:18]

### 4.1 User \& ACL

`core/models/user.py`:

```python
class User(Base):
    __tablename__ = "users"
    id = Column(UUID, primary_key=True)
    keycloak_id = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    display_name = Column(String)
    created_at = Column(DateTime, default=func.now())
```

`core/models/acl.py`:

```python
class Role(Base):
    __tablename__ = "roles"
    id = Column(UUID, primary_key=True)
    name = Column(String, unique=True)  # e.g., admin, manager, employee
    description = Column(Text)

class Permission(Base):
    __tablename__ = "permissions"
    id = Column(UUID, primary_key=True)
    key = Column(String, unique=True)  # e.g., tool:project.read
    description = Column(Text)

class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id = Column(UUID, ForeignKey("roles.id"), primary_key=True)
    permission_id = Column(UUID, ForeignKey("permissions.id"), primary_key=True)

class UserRole(Base):
    __tablename__ = "user_roles"
    user_id = Column(UUID, ForeignKey("users.id"), primary_key=True)
    role_id = Column(UUID, ForeignKey("roles.id"), primary_key=True)

class ToolAcl(Base):
    """
    Fine-grained ACL per tool/MCP function.
    """
    __tablename__ = "tool_acl"
    id = Column(UUID, primary_key=True)
    tool_name = Column(String, index=True)       # "email.send", "bash.exec"
    mcp_server = Column(String, nullable=True)
    mcp_tool = Column(String, nullable=True)
    allow_roles = Column(ARRAY(String))          # ["admin", "manager"]
    deny_roles = Column(ARRAY(String))           # optional
```


### 4.2 Workflows \& Canvas

`core/models/workflow.py`:

```python
class Workflow(Base):
    __tablename__ = "workflows"
    id = Column(UUID, primary_key=True)
    owner_id = Column(UUID, ForeignKey("users.id"))
    name = Column(String)
    description = Column(Text)
    is_public = Column(Boolean, default=False)
    definition_json = Column(JSON)  # Canvas JSON (nodes, edges, config)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    id = Column(UUID, primary_key=True)
    workflow_id = Column(UUID, ForeignKey("workflows.id"))
    user_id = Column(UUID, ForeignKey("users.id"))
    status = Column(String)  # pending/running/success/failed/paused
    started_at = Column(DateTime, default=func.now())
    finished_at = Column(DateTime, nullable=True)
    state_snapshot = Column(JSON)  # Serialized LangGraph state
    error_message = Column(Text, nullable=True)
```


### 4.3 Scheduler Jobs

`core/models/job.py`:

```python
class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"
    id = Column(UUID, primary_key=True)
    user_id = Column(UUID, ForeignKey("users.id"))
    workflow_id = Column(UUID, ForeignKey("workflows.id"))
    name = Column(String)
    schedule_cron = Column(String)    # e.g., "0 8 * * MON-FRI"
    timezone = Column(String, default="Asia/Ho_Chi_Minh")
    enabled = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    params = Column(JSON, nullable=True)  # Workflow-specific inputs
    delivery_channel = Column(String, nullable=True)  # "web", "telegram", etc.
```


### 4.4 Hierarchical Memory

`core/models/memory.py` implements three tiers with per‑user isolation.[file:15]

```python
class ShortTermMemory(Base):
    __tablename__ = "memory_short_term"
    id = Column(UUID, primary_key=True)
    user_id = Column(UUID, ForeignKey("users.id"), index=True)
    conversation_id = Column(UUID, index=True)
    content = Column(Text)          # raw messages (recent turns)
    created_at = Column(DateTime, default=func.now())

class MediumTermMemory(Base):
    __tablename__ = "memory_medium_term"
    id = Column(UUID, primary_key=True)
    user_id = Column(UUID, ForeignKey("users.id"), index=True)
    conversation_id = Column(UUID, index=True)
    summary = Column(Text)          # summarized sessions
    from_ts = Column(DateTime)
    to_ts = Column(DateTime)
    created_at = Column(DateTime, default=func.now())

class LongTermFact(Base):
    __tablename__ = "memory_long_term"
    id = Column(UUID, primary_key=True)
    user_id = Column(UUID, ForeignKey("users.id"), index=True)
    fact_key = Column(String, index=True)   # "preferred_language", etc.
    fact_value = Column(Text)
    embedding = Column(ARRAY(Float), nullable=True)  # if using PgVector
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
```

Memory access routines in `memory/short_term.py`, `memory/medium_term.py`, `memory/long_term.py` enforce that all queries are filtered by `user_id` and optionally RBAC.[file:15]

### 4.5 Channels

`core/models/channel.py`:

```python
class ChannelAccount(Base):
    __tablename__ = "channel_accounts"
    id = Column(UUID, primary_key=True)
    user_id = Column(UUID, ForeignKey("users.id"))
    channel_type = Column(String)  # "telegram", "whatsapp", "slack"
    external_user_id = Column(String)  # e.g., telegram chat_id
    metadata = Column(JSON)
    created_at = Column(DateTime, default=func.now())

class ChannelSession(Base):
    __tablename__ = "channel_sessions"
    id = Column(UUID, primary_key=True)
    channel_account_id = Column(UUID, ForeignKey("channel_accounts.id"))
    conversation_id = Column(UUID, index=True)  # maps to AG-UI thread
    last_activity_at = Column(DateTime, default=func.now())
```


---

## 5. Security \& Gateway Modules

### 5.1 Keycloak Integration

`security/keycloak_client.py`:

- Functions to fetch JWKS, verify tokens, introspect roles.
- Caches Keycloak public keys.

`security/jwt.py`:

- `decode_token(token) -> TokenClaims`
- Validates signature, expiry, issuer, audience.

`security/rbac.py`:

- Maps Keycloak roles to Blitz roles \& permissions.
- Helper: `has_permission(user, "tool:project.read")`.

`security/acl.py`:

- Checks `ToolAcl` for tool name and user roles.

`security/deps.py`:

- FastAPI dependencies:
    - `get_current_user()` (validate JWT, load User)
    - `require_permission("tool:...")`


### 5.2 Copilot Runtime \& AG‑UI Middleware

`gateway/runtime.py`:

- Initializes Copilot Runtime and LangGraph integration.
- Responsible for mapping AG‑UI events (`TOOLCALL_START`, etc.) to LangGraph tool calls.

`gateway/agui_middleware.py`:

- FastAPI middleware that:
    - Reads JWT from headers for all AG‑UI endpoints.
    - Injects user context into the request state.
    - On TOOL calls, runs RBAC + ACL checks before allowing execution.[file:1][file:11]

`gateway/tool_registry.py`:

- Maps tool names (email.send, calendar.list, mcp.crm.search) to Python functions or MCP tools.
- Also captures metadata (required permissions, sandbox flag).

---

## 6. Agents \& LangGraph

### 6.1 Master Agent

`agents/master_agent.py`:

- Uses `create_deep_agent(...)` with:
    - Planner (high‑level task decomposition)
    - File‑based context (temporary FS for each run)
    - Sub‑agent spawning (call `email_agent`, `project_agent`, etc.)[file:18]

Key entrypoints:

- `run_conversation(user_context, input_message)` for chat.
- `run_workflow(workflow_id, params, user_context)` for scheduled jobs.


### 6.2 StateGraph \& Canvas Mapping

`agents/graphs.py`:

- Functions to compile a stored `Workflow.definition_json` (canvas JSON) into a LangGraph `StateGraph`.[file:18][file:17]

```python
def compile_workflow_to_stategraph(workflow: Workflow) -> StateGraph:
    # 1. Parse nodes & edges from workflow.definition_json
    # 2. Map node type -> LangGraph node:
    #    - "agent" -> sub-agent
    #    - "tool"  -> backend tool
    #    - "mcp"   -> MCP call
    #    - "hitl"  -> human approval node
    # 3. Wire edges as transitions based on success/failure paths
    return stategraph
```

`agents/state/types.py`:

- Shared state definitions passed between nodes, e.g.:

```python
class BlitzState(TypedDict):
    user_id: str
    conversation_id: str
    context: dict
    last_output: Any
```


### 6.3 Sub‑Agents

`agents/subagents/`:

- `email_agent.py`: email workflows (morning digest, follow‑ups)
- `calendar_agent.py`: calendar summarization \& scheduling
- `project_agent.py`: project/task management workflows
- `channel_agent.py`: multi‑channel messaging logic

Each sub‑agent defines its own tools \& LangGraph nodes but remains orchestrated by `master_agent.py` for complex tasks.

---

## 7. Backend Tools \& Sandbox

### 7.1 Tool Modules

`tools/email_tools.py`:

- `@tool def fetch_emails(...)`
- `@tool def send_email(...)`

`tools/calendar_tools.py`:

- `@tool def list_events(...)`
- `@tool def summarize_day(...)`

`tools/project_tools.py`:

- `@tool def create_task(...)`
- `@tool def update_status(...)`

`tools/dataops_tools.py`:

- Safe DB queries, analytics tasks, CSV exports.

Each tool:

- Has a Pydantic input/output schema in `core/schemas/*.py` for validation.[file:7][file:18]
- Has metadata in `tool_registry` specifying required permissions and whether sandboxing is required.


### 7.2 Sandbox Execution

`tools/sandbox_tools.py`:

- High‑risk tools: `bash.exec`, `python.exec`, code evaluation, data transformations requiring arbitrary code.

`sandbox/docker_client.py`:

- Wraps Docker SDK to:
    - Start short‑lived containers (per session or per request).
    - Enforce CPU, memory, network limits.[file:14]

`sandbox/policies.py`:

- Defines which tools must run in sandbox (denylist/allowlist).
- Minimal base images (OpenClaw‑style: `sandbox-common`, `sandbox-browser`).[file:14]

`sandbox/executor.py`:

- Accepts a “tool job” (user, script, environment), executes in Docker, returns stdout/stderr.

---

## 8. MCP Integration

`mcp/client.py`:

- Generic MCP client to:
    - List tools for a given MCP server.
    - Call tools with structured inputs.
    - Handle streaming responses if needed.[file:1][file:18]

`mcp/servers/*.py`:

- Optional local MCP servers:
    - `crm_server.py` – internal CRM DB
    - `docs_server.py` – document store

Corresponding tool entries in `tool_registry` ensure RBAC/ACL for each MCP tool.[file:7]

---

## 9. Scheduler Subsystem

`scheduler/celery_app.py`:

- Configures Celery with Redis.
- Task: `run_scheduled_job(job_id)`.

`scheduler/jobs.py`:

- Logic to compute `next_run_at` from cron.
- Helper: `enqueue_due_jobs()` (if needed for periodic scanning).

`scheduler/worker.py`:

- Celery worker execution:
    - Load `ScheduledJob` and `Workflow`.
    - Build user context (load user \& roles).
    - Compile workflow to StateGraph and run via `master_agent.run_workflow`.
    - Persist `WorkflowRun` and update job’s `last_run_at` / `next_run_at`.
    - Deliver results via:
        - A2UI notification (web)
        - Channel dispatcher (Telegram/WhatsApp/Slack)

---

## 10. Channels \& Gateways

### 10.1 Backend Channel Dispatcher

`channels/dispatcher.py`:

- Called by agents and scheduler when they need to send a message via channel.

```python
def send_message(user_id: str, channel: str, payload: dict):
    # Resolve ChannelAccount via user_id & channel
    # Call channel-specific adapter (telegram_adapter, etc.)
```

`channels/models.py`:

- Shared Pydantic models for channel payloads (simple text vs rich UI).


### 10.2 External Channel Gateways (Optional)

`channel-gateways/telegram/` (separate service):

```text
channel-gateways/telegram/
  app.py
  config.py
  handlers.py
```

- Receives Telegram updates → resolves to Blitz user (via `ChannelAccount`).
- Calls `backend/api/channels.py` endpoint with text + metadata.
- For outbound: listens to backend webhook or polls a queue.

`backend/api/routes/channels.py`:

- Unified “incoming message” endpoint called by all channels:
    - Validates signature/auth of the gateway.
    - Resolves `ChannelAccount` and `User`.
    - Calls `master_agent.run_conversation` with channel context.
    - Returns text/A2UI spec which gateway renders or simplifies.

---

## 11. Frontend Structure (Next.js + CopilotKit)

Frontend hosts the low‑code canvas, chat, and A2UI rendering.[file:1][file:17][file:13]

```text
frontend/
  next.config.js
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


### 11.1 Copilot Provider \& Auth

`hooks/use-copilot-provider.ts`:

- Wraps CopilotKit provider with Keycloak session.
- Ensures JWT is attached to all AG‑UI calls.[file:11]

`app/layout.tsx`:

- Registers provider; sets up SSE/WebSocket endpoints to FastAPI.


### 11.2 Canvas Components

`components/canvas/`:

- Renders workflow graph (nodes, edges).
- Uses `useCoAgent` to sync canvas state with LangGraph StateGraph.[file:17]
- Workflow definition JSON is what gets persisted in `Workflow.definition_json` and compiled on the backend.[file:18]

`hooks/use-frontend-tools.ts`:

- Registers skills via `useFrontendTool` for:
    - `addNode`, `updateNode`, `deleteNode`
    - Zoom, pan, selection, etc.[file:17]


### 11.3 Chat \& A2UI

`components/chat/`:

- Standard AG‑UI chat (messages, streaming, tool call visualization).

`components/a2ui/A2UIMessageRenderer.tsx`:

- Parses A2UI JSONL (surfaceUpdate, dataModelUpdate).
- Maps them to React components in `widgets/`.[file:13]

---

## 12. API Routes (Backend)

Key endpoints for MVP:

- `POST /api/agents/chat` – AG‑UI chat endpoint.
- `POST /api/workflows` – create/update workflow (canvas).
- `GET /api/workflows/{id}` – get workflow definition.
- `POST /api/workflows/{id}/run` – run workflow once.
- `POST /api/scheduler/jobs` – create/update scheduled job.
- `GET /api/scheduler/jobs` – list jobs per user.
- `POST /api/channels/incoming` – channel gateways send inbound messages.
- `POST /api/mcp/tools/{name}` – optional direct MCP tool call for testing.

All endpoints use `get_current_user()` and `require_permission(...)` where appropriate.[file:11]

---

## 13. Security \& Data Isolation Notes

- Every tool and MCP call goes through:

1. JWT validation
2. RBAC permission check
3. Tool ACL check per `tool_registry` and `ToolAcl` table.[file:1][file:7][file:11]
- Memory routines only ever query by `user_id` from the token; no cross‑user reads are allowed by design.[file:15]
- Sandbox enforced for any tool marked `sandbox_required=True` in `tool_registry`.
- Scheduler runs as a service account but always executes workflows with the original owner’s user context (for memory and ACL).

---

## 14. Suggested MVP Scope

For initial implementation at Blitz:

1. **Agents**
    - Master agent + `email_agent`, `calendar_agent`, `project_agent`.
2. **Tools**
    - Email read/send (via company provider), calendar list, basic task CRUD.
3. **Memory**
    - Short‑term and medium‑term tables; long‑term facts for user preferences.
4. **Scheduler**
    - Cron‑based morning digest and daily project summary.
5. **Channels**
    - Start with web UI only; then add one external channel (e.g., Telegram).
6. **Security**
    - Keycloak realm, JWT validation middleware, role/permission mapping, basic tool ACL.

This structure should be sufficient for architects and developers to begin detailed design sessions, define concrete schemas, and start prototyping services.

```markdown
<span style="display:none">[^1][^2][^3]</span>

<div align="center">⁂</div>

[^1]: 01-Kien-Truc-Ung-Dung-Agentic-Doanh-Nghiep-On-Premise.md
[^2]: 18-Cau-Truc-He-Thong-Agentic-Enterprise-Da-Nen-Tang.md
[^3]: 04-Quan-Tri-Bo-Nho-Phan-Cap-Cho-Agent-AI-Doanh-Nghiep.md```

