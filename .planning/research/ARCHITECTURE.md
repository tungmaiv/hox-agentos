# Architecture Patterns

**Domain:** Platform Enhancement & Infrastructure for Blitz AgentOS v1.4
**Researched:** 2026-03-15

---

## Recommended Architecture

The 9 v1.4 features integrate into the existing 5-layer architecture without requiring structural changes to the layer model. No new Docker services are needed except MinIO (for Storage #19) and an email sidecar (for Email #18). All features extend existing layers rather than adding new ones.

### System Context: v1.4 Feature Placement in Existing Layers

```
LAYER 1: FRONTEND (Next.js 15 + CopilotKit)
  MODIFIED:
    - Multi-Agent Tab Architecture (#16) -- MultiAgentWizard replaces single artifact-wizard
    - Admin Registry Edit UI (#06) -- detail/edit pages for all registry types
    - Scheduler UI (#15) -- /admin/scheduler page + per-workflow schedule tab
    - Unified Dashboard (#08+#14) -- /dashboard page with Tremor charts + WebSocket
    - UX Enhancement (#13) -- CSS variable theming, avatar upload, timezone picker
    - Permission Approval UI (#01) -- admin notification badge + approval drawer
    - Email Settings UI (#18) -- email account pairing in /settings/channels
  NEW PAGES:
    - /dashboard (Mission Control + Analytics tabs)
    - /admin/scheduler (global scheduler view)
    - /storage (file manager -- #19)

LAYER 2: SECURITY RUNTIME (FastAPI + Keycloak + RBAC + ACL)
  MODIFIED:
    - Keycloak Hardening (#07) -- circuit breaker in jwt.py, health categorization
    - Permission Approval (#01) -- Gate 3 escalation path (pause instead of deny)
    - tool_acl table gains temporal columns (duration_type, expires_at, granted_at)
  NEW:
    - CircuitBreaker class in security/
    - PermissionRequestService in security/
    - KeycloakHealthMonitor in security/

LAYER 3: AGENT ORCHESTRATION (LangGraph + CopilotKit)
  MODIFIED:
    - Multi-Agent Tab (#16) -- new tool_builder + mcp_builder agents alongside artifact_builder
    - Permission Approval (#01) -- LangGraph interrupt on permission denial
  NEW:
    - backend/agents/tool_builder.py
    - backend/agents/mcp_builder.py

LAYER 4: TOOLS, MEMORY, LLM GATEWAY
  MODIFIED:
    - Storage Service (#19) -- new storage adapter + memory file links
    - Email System (#18) -- email tools become real (replace mocks)
  NEW:
    - backend/storage/ module (integrated into main backend, not a sidecar)
    - backend/channels/email/ adapter

LAYER 5: INFRASTRUCTURE
  EXISTING (no changes): PostgreSQL, Redis, Keycloak, Celery, LiteLLM, Ollama
  NEW:
    - MinIO Docker service (#19) -- S3-compatible object storage
    - Email sidecar Docker service (#18) -- IMAP/SMTP handler
```

---

## Component Boundaries

### New Components

| Component | Responsibility | Communicates With | Feature |
|-----------|---------------|-------------------|---------|
| `CircuitBreaker` | Keycloak connection resilience | `security/jwt.py`, `admin_keycloak.py` | #07 |
| `KeycloakHealthMonitor` | Categorize SSO health states | `CircuitBreaker`, admin dashboard | #07 |
| `PermissionRequestService` | Create/approve/reject permission escalations | Gate 3 ACL, admin UI, LangGraph interrupt | #01 |
| `AutoApproveEngine` | Evaluate auto-approve rules for low-risk tools | `PermissionRequestService` | #01 |
| `ToolBuilderAgent` | Dedicated LangGraph agent for tool creation | CopilotKit (separate instance), registry | #16 |
| `MCPBuilderAgent` | Dedicated LangGraph agent for MCP server creation | CopilotKit (separate instance), registry | #16 |
| `AgentDependencyService` | Track parent-child artifact dependencies | `tool_builder`, `mcp_builder`, `artifact_builder` | #16 |
| `SchedulerDashboardService` | Aggregate scheduler metrics + execution history | Celery, `workflow_triggers`, `workflow_runs` | #15 |
| `DashboardWebSocketManager` | Real-time activity feed via WebSocket | Frontend dashboard, agent events, workflow events | #08+#14 |
| `ThemeService` | Store/retrieve user theme preferences | `user_preferences` table, frontend CSS vars | #13 |
| `StorageAdapter` (Protocol) | Abstract file storage operations | MinIO, future S3/Azure | #19 |
| `MinIOStorageAdapter` | MinIO-specific storage implementation | MinIO Docker service | #19 |
| `StorageService` | File/folder CRUD with ACL enforcement | `StorageAdapter`, PostgreSQL, memory service | #19 |
| `EmailSidecar` | IMAP/SMTP email handling | Backend via REST, Google/Microsoft OAuth | #18 |
| `NotificationRouter` | Route notifications to preferred channels | Email sidecar, Telegram, in-app | #18 |

### Modified Components

| Component | Current Location | What Changes | Feature |
|-----------|-----------------|--------------|---------|
| `security/jwt.py` | `backend/security/jwt.py` | Add circuit breaker wrapping JWKS fetch | #07 |
| `gateway/agui_middleware.py` | `backend/gateway/` | Gate 3 returns "escalate" instead of "deny" when configured | #01 |
| `tool_acl` model | `backend/core/models/tool_acl.py` | Add `duration_type`, `expires_at`, `granted_at` columns | #01 |
| `artifact_builder.py` | `backend/agents/` | Add missing-dependency detection phase | #16 |
| `artifact-wizard.tsx` | `frontend/src/components/admin/` | Replaced by `MultiAgentWizard` (backward-compatible) | #16 |
| `workflow_routes.py` | `backend/api/routes/workflows.py` | Add scheduler management endpoints | #15 |
| `celery_app.py` | `backend/scheduler/celery_app.py` | Expose queue stats via API | #15 |
| `user_preferences` model | `backend/core/models/user_preferences.py` | Add `theme`, `timezone`, `avatar_url` columns | #13 |
| `email_tools.py` | `backend/tools/` | Replace mock data with real OAuth email calls | #18 |
| `channel_accounts` model | `backend/core/models/channel.py` | Add email account type support | #18 |

---

## Data Flow Changes

### 1. Permission Approval Flow (NEW -- #01)

```
User/Agent invokes tool
  |
  v
Gate 1: JWT validation (unchanged)
  |
  v
Gate 2: RBAC check (unchanged)
  |
  v
Gate 3: Tool ACL check
  |
  +-- ALLOWED --> Execute tool (unchanged)
  |
  +-- DENIED (old behavior) --> 403
  |
  +-- ESCALATE (new behavior) -->
        |
        v
      Create PermissionRequest in DB
        |
        v
      LangGraph interrupt (pause execution)
        |
        v
      Notify admin (WebSocket badge + optional Telegram/email)
        |
        v
      Admin reviews context --> Approve or Reject
        |
        +-- APPROVE --> Create ToolAcl entry (with expiration) --> Resume LangGraph
        +-- REJECT  --> Create ToolAcl(allowed=False) --> Fail with message
```

**New DB tables:** `permission_requests`, `auto_approve_rules`
**Modified tables:** `tool_acl` (add temporal columns)

### 2. Multi-Agent Tab Flow (NEW -- #16)

```
User opens /admin/create
  |
  v
MultiAgentWizard creates parent tab (CopilotKit instance 1)
  |
  v
Skill builder detects missing tool dependency
  |
  v
POST /api/agent-dependencies (create pending dependency)
  |
  v
UI shows "Create Tool" button
  |
  v
User clicks --> spawnChildTab (CopilotKit instance 2)
  |
  v
Tool builder agent runs in isolated context
  |
  v
Tool created --> POST /api/agent-dependencies/{id}/completed
  |
  v
Parent tab polls, sees completion --> resume skill creation
```

**New DB table:** `agent_dependencies`
**Key constraint:** Max 5 concurrent CopilotKit instances (performance)

### 3. Keycloak Circuit Breaker Flow (MODIFIED -- #07)

```
Login request arrives
  |
  v
Check CircuitBreaker state
  |
  +-- CLOSED (healthy) --> Normal JWKS fetch + SSO
  |
  +-- OPEN (failing) --> Skip SSO, show local auth only
  |                       (SSO button hidden or grayed out)
  |
  +-- HALF-OPEN (testing) --> Try one JWKS fetch
        |
        +-- Success --> CLOSED (restore SSO)
        +-- Failure --> OPEN (stay down, increment timer)

Admin sees health status in /admin/identity:
  - GREEN: SSO healthy
  - YELLOW: Intermittent (half-open)
  - RED: SSO unavailable (circuit open)
  - GRAY: Not configured (no Keycloak)
```

**No new tables.** State held in-memory (single backend process).

### 4. Unified Dashboard Real-Time Flow (NEW -- #08+#14)

```
Backend events (agent actions, workflow runs, tool calls)
  |
  v
structlog JSON audit events (existing)
  |
  v
DashboardWebSocketManager broadcasts to connected clients
  |
  v
Frontend /dashboard receives via WebSocket
  |
  v
Tremor charts update in real-time
  |
  +-- Activity Feed: chronological event stream
  +-- Metrics Cards: counters (agents active, workflows running, etc.)
  +-- Execution Monitor: drill-down into workflow step progress
```

**Data sources (all existing, just surfaced):**
- `workflow_runs` table (execution history)
- `memory_conversations` table (agent activity)
- Prometheus metrics (system health)
- structlog JSON files (audit trail)

**New backend component:** WebSocket endpoint at `/ws/dashboard`
**New frontend dependency:** Tremor React charts library

### 5. Storage Service Flow (NEW -- #19)

```
User uploads file via /storage UI
  |
  v
POST /api/storage/files/upload (multipart)
  |
  v
StorageService validates ownership + ACL
  |
  v
MinIOStorageAdapter.upload() --> MinIO bucket
  |
  v
Create File record in PostgreSQL (metadata only)
  |
  v
User clicks "Add to Memory"
  |
  v
StorageService downloads from MinIO
  |
  v
Sends to embedding sidecar (bge-m3) via existing memory service
  |
  v
Creates MemoryFileLink in PostgreSQL
```

**New Docker service:** MinIO (port 9000 API / 9001 console)
**New DB tables:** `files`, `folders`, `file_folder_links`, `file_shares`, `memory_file_links`
**Port conflict note:** Storage spec says port 8001, but MCP CRM is already on 8001. Integrate storage routes into main backend under `/api/storage/*` instead.

### 6. Email System Flow (NEW -- #18)

```
Email sidecar (Docker service, port 8003)
  |
  +-- IMAP IDLE: monitors user mailboxes
  |     |
  |     v
  |   New email arrives --> POST /api/channels/incoming (existing pattern)
  |     |
  |     v
  |   Channel gateway routes to master agent (existing flow)
  |
  +-- SMTP: agent sends email
        |
        v
      Backend calls email sidecar REST API
        |
        v
      Email sidecar sends via SMTP (OAuth authenticated)

User configures email account:
  /settings/channels --> OAuth flow (Google/Microsoft)
  |
  v
  Store OAuth tokens in user_credentials (AES-256 encrypted, existing pattern)
```

**New Docker service:** email-sidecar (Python, port 8003)
**Modified tables:** `channel_accounts` (add email type)
**Uses existing:** `user_credentials` table, channel adapter pattern

---

## Patterns to Follow

### Pattern 1: Circuit Breaker (for Keycloak #07)

Use a simple state-machine circuit breaker. Do NOT add a library dependency (pybreaker, etc.) -- this is a single integration point.

```python
# backend/security/circuit_breaker.py
class CircuitBreaker:
    """Simple circuit breaker for Keycloak JWKS fetch."""

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: int = 60,  # seconds
    ):
        self.state: Literal["closed", "open", "half_open"] = "closed"
        self.failure_count: int = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time: float | None = None

    async def call(self, func: Callable, *args, **kwargs):
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half_open"
            else:
                raise CircuitOpenError("Keycloak circuit is open")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
```

**When to use:** Any external service dependency that can be temporarily unavailable.
**Where NOT to use:** PostgreSQL, Redis (these are infrastructure -- if they're down, the app is down).

### Pattern 2: LangGraph Interrupt for Permission Escalation (#01)

Use LangGraph's built-in interrupt mechanism (same pattern as existing HITL workflow nodes).

```python
# In gateway/agui_middleware.py, modify Gate 3
async def check_tool_permission(user_id: UUID, tool_name: str) -> PermissionResult:
    acl = await get_tool_acl(user_id, tool_name)
    if acl and acl.allowed:
        # Check expiration for temporal ACLs
        if acl.expires_at and acl.expires_at < datetime.utcnow():
            await expire_acl(acl)
        else:
            return PermissionResult(granted=True)
    if acl and not acl.allowed:
        return PermissionResult(granted=False, reason="explicitly_denied")

    # No ACL entry -- check auto-approve rules first
    auto_rule = await auto_approve_engine.evaluate(user_id, tool_name)
    if auto_rule:
        await create_acl_from_rule(user_id, tool_name, auto_rule)
        return PermissionResult(granted=True, auto_approved=True)

    # No auto-approve -- create escalation request
    request = await permission_request_service.create(
        user_id=user_id,
        tool_name=tool_name,
        context=build_context(user_id, tool_name),
    )
    return PermissionResult(
        granted=False,
        escalatable=True,
        request_id=request.id,
    )
```

### Pattern 3: WebSocket for Real-Time Dashboard (#08+#14)

Use FastAPI's native WebSocket support. Do NOT add Socket.IO or a separate WebSocket service.

```python
# backend/api/routes/dashboard_ws.py
from fastapi import WebSocket, WebSocketDisconnect

class DashboardManager:
    def __init__(self):
        self.connections: dict[str, WebSocket] = {}  # user_id -> ws

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.connections[user_id] = websocket

    async def broadcast(self, event: dict):
        disconnected = []
        for uid, ws in self.connections.items():
            try:
                await ws.send_json(event)
            except WebSocketDisconnect:
                disconnected.append(uid)
        for uid in disconnected:
            del self.connections[uid]
```

**Why native WebSocket:** 100 users max. No need for Socket.IO's room/namespace complexity. FastAPI WebSocket is sufficient and adds zero dependencies.

### Pattern 4: CSS Variable Theming (#13)

Use Tailwind v4 CSS custom properties. No runtime theme provider needed.

```css
/* Apply theme before React hydration via <script> in layout.tsx */
:root {
  --color-primary: 59 130 246;      /* blue-500 */
  --color-background: 255 255 255;  /* white */
  --color-surface: 249 250 251;     /* gray-50 */
  --color-text: 17 24 39;           /* gray-900 */
}

[data-theme="dark"] {
  --color-primary: 96 165 250;      /* blue-400 */
  --color-background: 17 24 39;     /* gray-900 */
  --color-surface: 31 41 55;        /* gray-800 */
  --color-text: 243 244 246;        /* gray-100 */
}
```

**Key decision:** Apply theme via `data-theme` attribute on `<html>`, set by a blocking `<script>` that reads localStorage BEFORE React hydrates. This prevents flash-of-wrong-theme.

### Pattern 5: Storage Adapter Protocol (#19)

Follow the existing `ChannelAdapter` pattern. Protocol-based, not ABC. Register in a factory.

```python
class StorageAdapter(Protocol):
    adapter_name: str

    async def upload(self, key: str, content: BytesIO, content_type: str) -> str: ...
    async def download(self, key: str) -> BytesIO: ...
    async def delete(self, key: str) -> None: ...
    async def get_presigned_url(self, key: str, expires: int = 3600) -> str: ...
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Separate Microservice for Storage
**What:** Running storage service as an independent FastAPI app on its own port
**Why bad:** At 100-user scale, a separate service adds Docker Compose complexity, cross-service auth, network hops, and deployment coordination -- all for zero scaling benefit. Port 8001 is already taken by MCP CRM.
**Instead:** Integrate storage routes directly into the main backend FastAPI app under `/api/storage/*`. Storage adapter talks to MinIO; models live in the shared PostgreSQL. The only new Docker service is MinIO itself.

### Anti-Pattern 2: Redis-backed Circuit Breaker State
**What:** Storing circuit breaker state in Redis for "multi-instance" support
**Why bad:** There's one backend instance in Docker Compose. Adding Redis state for a circuit breaker that protects a single Keycloak is over-engineering.
**Instead:** In-memory state on the single backend process. If you scale to multiple backend instances post-MVP, then add Redis state.

### Anti-Pattern 3: Polling for Dashboard Updates
**What:** Frontend polling `/api/dashboard/events` every 2-5 seconds
**Why bad:** 100 users polling every 2 seconds = 50 requests/second for zero-change responses. Wasteful.
**Instead:** WebSocket connection from dashboard page. Backend pushes events as they happen. Falls back to polling only if WebSocket disconnects.

### Anti-Pattern 4: Multiple CopilotKit Providers Mounted Simultaneously
**What:** Rendering all agent tabs simultaneously with separate `<CopilotKit>` providers
**Why bad:** Each CopilotKit instance opens a persistent SSE connection and maintains state. 5 tabs = 5 active connections.
**Instead:** Only mount the active tab's `<CopilotKit>` provider. Use `key={tab.sessionId}` to force fresh instances, but unmount inactive tabs. Preserve form state in React state or sessionStorage, not in CopilotKit.

### Anti-Pattern 5: Grafana Iframe Embedding for Analytics
**What:** Embedding Grafana panels via `<iframe>` in the Next.js dashboard
**Why bad:** Grafana iframes require separate auth (anonymous access or auth proxy), look visually inconsistent, and cannot be styled to match the AgentOS theme.
**Instead:** Query Prometheus metrics directly from backend API endpoints, render with Tremor React charts. Keep Grafana for ops team deep-dives at port 3001.

### Anti-Pattern 6: Module/Sidecar Pattern for LLM Config
**What:** The Topic #04 spec proposes a `BaseModule` sidecar pattern with Redis module registry
**Why bad:** Introduces a new architectural pattern (module sidecars) not used anywhere else. Over-engineers for a single config page.
**Instead:** Standard FastAPI routes + `platform_config` table. LLM config already has `/api/admin/llm/models` routes -- extend those.

---

## Database Schema Changes Summary

### New Tables (7-8)

| Table | Feature | Key Columns | Relationships |
|-------|---------|-------------|---------------|
| `permission_requests` | #01 | id, user_id, tool_name, status, context_json, admin_response_json, created_at, resolved_at | FK to tool_acl on approval |
| `auto_approve_rules` | #01 | id, tool_pattern, role_pattern, max_duration, is_active | Evaluated by AutoApproveEngine |
| `agent_dependencies` | #16 | id, parent_session_id, child_session_id, dependency_name, dependency_type, status, context_payload, result_payload | No FK (session-based) |
| `files` | #19 | id, bucket_path, owner_id, original_name, mime_type, size, hash, status | FK from file_folder_links, file_shares, memory_file_links |
| `folders` | #19 | id, parent_id, owner_id, name, folder_type | Self-referential FK (parent_id) |
| `file_folder_links` | #19 | file_id, folder_id | FK to files, folders |
| `file_shares` | #19 | id, file_id, owner_id, recipient_id, permission | FK to files |
| `memory_file_links` | #19 | memory_record_id, file_id | FK to memory_facts, files |

### Modified Tables (2)

| Table | Feature | Changes |
|-------|---------|---------|
| `tool_acl` | #01 | Add: `duration_type` (enum), `expires_at` (timestamp nullable), `granted_at` (timestamp), `granted_by` (UUID nullable) |
| `user_preferences` | #13 | Add: `theme` (varchar, default 'system'), `timezone` (varchar, default 'UTC'), `avatar_url` (varchar nullable) |

### Migration Strategy

Current state: 2 active Alembic heads needing merge (`617b296e937a` + `83f730920f5a`).

```
617b296e937a (030) + 83f730920f5a (platform_config)
    |
    v
031_merge_heads (merge migration -- required first step)
    |
    v
032_permission_approval (tool_acl temporal columns + permission_requests + auto_approve_rules)
    |
    v
033_agent_dependencies (agent_dependencies table)
    |
    v
034_user_experience (user_preferences additions: theme, timezone, avatar_url)
    |
    v
035_storage_tables (files, folders, file_folder_links, file_shares, memory_file_links)
    |
    v
036_email_channel (channel_accounts email type, notification_preferences if needed)
```

**Critical:** The merge migration (031) must happen before any v1.4 work. Without it, `alembic upgrade head` will fail with multiple heads error.

---

## Integration Dependency Graph

```
                    #07 Keycloak Hardening (no dependencies)
                         |
                         v
              #06 Admin Registry Edit UI (no dependencies)
                         |
                         v
              #01 Permission Approval HITL (stable auth required)
                    |         |
                    v         v
        #15 Scheduler UI   #16 Multi-Agent Tabs
           (independent)     (independent)
                    |         |
                    v         v
        #13 UX Enhancement  #08+#14 Unified Dashboard
           (additive)       (benefits from #15 scheduler data)
                    |
                    v
              #19 Storage Service (MinIO; avatar from #13 can use same MinIO)
                    |
                    v
              #18 Email System (needs OAuth setup, uses notification routing)
```

### Dependency Rationale

1. **#07 first** -- Keycloak hardening is pure backend resilience with zero feature dependencies. Stabilizes auth before adding features that need stable auth.

2. **#06 early** -- Registry edit UI is a quick win that improves admin workflow for all subsequent features (editing tools, MCP servers created by #16).

3. **#01 after #07** -- Permission approval modifies Gate 3 (core security layer). Keycloak must be stable first. No point escalating permissions if auth itself is flaky.

4. **#15 and #16 can be parallel after #01** -- Both are independent. #15 adds UI on existing Celery infrastructure. #16 refactors the artifact builder. Neither depends on the other.

5. **#13 mid-milestone** -- UX enhancement (theme, avatars) is additive polish. Do after core functionality is stable. Avatar upload needs MinIO, but can start with local filesystem and migrate to MinIO when #19 lands.

6. **#08+#14 after #15** -- Dashboard surfaces scheduler data, workflow execution data, and agent activity. Building the dashboard before the scheduler UI means the dashboard data story is incomplete.

7. **#19 late** -- Storage service is the largest infrastructure addition (new Docker service, 5 new tables, file manager UI). Contains blast radius by doing it after core features stabilize.

8. **#18 last** -- Email system requires external OAuth setup (Google Cloud Console, Azure AD app registration), a new Docker sidecar, and notification routing that benefits from the dashboard (#08+#14).

---

## Suggested Build Order (Phases)

### Phase A: Foundation Hardening (2-3 weeks)
- **#07 Keycloak SSO Hardening** -- Circuit breaker, health monitoring, config validation
- **#06 Admin Registry Edit UI** -- Detail/edit pages, MCP connection testing

**Rationale:** Both are independent, low-risk, high-value admin improvements. Can run in parallel.

### Phase B: Security Enhancement (2-3 weeks)
- **#01 Runtime Permission Approval HITL** -- Temporal ACL, permission request queue, auto-approve rules

**Rationale:** Modifies the Gate 3 security layer. Must be stable and tested before adding more agent types (#16) that will trigger permission checks.

### Phase C: Core Features (3-4 weeks, parallel tracks)
- **Track 1: #15 Scheduler UI & Management APIs** -- Cron builder, execution history, queue monitoring
- **Track 2: #16 Multi-Agent Tab Architecture** -- tool_builder, mcp_builder agents, tabbed wizard UI

**Rationale:** Independent features with no overlap. #15 is purely UI on existing backend. #16 is agent architecture + frontend tabs.

### Phase D: Experience & Visibility (3-4 weeks, parallel tracks)
- **Track 1: #13 UX Enhancement** -- Dark theme, timezone, avatar upload
- **Track 2: #08+#14 Unified Dashboard** -- Mission Control + Analytics, WebSocket feed, Tremor charts

**Rationale:** Polish and visibility layer. Dashboard benefits from having scheduler data (#15) and permission events (#01) to display.

### Phase E: Infrastructure (4-5 weeks)
- **#19 Storage Service** -- MinIO deployment, file/folder models, storage adapter, file manager UI

**Rationale:** Largest infrastructure addition. Separate phase to contain blast radius. Can reuse MinIO that #13 avatar upload may have introduced.

### Phase F: Email & Notifications (3-4 weeks)
- **#18 Email System & Notifications** -- Email sidecar, OAuth, notification routing

**Rationale:** Requires external OAuth setup (long lead time). Benefits from storage service (#19 for attachments), dashboard (#08+#14 for notification UI), and channel architecture maturity.

---

## Scalability Considerations

| Concern | At 10 users | At 100 users | At 500+ users (post-MVP) |
|---------|-------------|--------------|--------------------------|
| WebSocket connections | Trivial | ~100 persistent conns, single process fine | Need Redis pub/sub for multi-process |
| CopilotKit instances | 1-2 per user | 100-200 SSE connections | Connection pooling needed |
| MinIO storage | Single bucket | Single bucket, ~10GB | Add lifecycle policies |
| Permission requests | <10/day | <100/day | Auto-approve rules critical |
| Circuit breaker state | In-memory | In-memory (single process) | Redis-backed for multi-process |
| Dashboard metrics | Direct DB queries | Direct DB queries | Materialized views for aggregates |
| Email sidecar IMAP | Few mailboxes | ~100 IMAP connections | Connection pooling, dedicated workers |

---

## Technology Additions

| Technology | Feature | Purpose | Why This Over Alternatives |
|------------|---------|---------|---------------------------|
| **Tremor React** | #08+#14 | Dashboard charts | Tailwind-native, Server Component compatible, no D3 complexity |
| **MinIO** | #19 | Object storage | S3-compatible, self-hosted (on-premise requirement), Docker image available |
| **`minio` Python SDK** | #19 | Storage adapter | Official SDK, thread pool for async |
| **`aiosmtplib`** | #18 | Email sending | Async SMTP for FastAPI compatibility |
| **`aioimaplib`** | #18 | Email receiving | Async IMAP with IDLE support |
| **FastAPI WebSocket** | #08+#14 | Real-time dashboard | Built-in, zero additional dependencies |

**No new frontend frameworks.** Tremor is the only UI library addition (Tailwind-based).
**No new backend frameworks.** All features use FastAPI, SQLAlchemy, Celery (existing stack).

---

## Sources

- Project architecture: `docs/architecture/architecture.md` (v1.0, 2026-02-24) -- HIGH confidence
- Enhancement specifications: `docs/enhancement/topics/*/00-specification.md` -- HIGH confidence (first-party design docs)
- Analysis report: `docs/enhancement/ANALYSIS-REPORT.md` -- HIGH confidence
- Current codebase structure: direct filesystem inspection -- HIGH confidence
- Docker Compose service inventory: `docker-compose.yml` -- HIGH confidence
- Existing DB schema: `docs/dev-context.md` Section 5 -- HIGH confidence
- Alembic migration state: CLAUDE.md Section 13 -- HIGH confidence
