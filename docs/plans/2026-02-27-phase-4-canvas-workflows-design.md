# Phase 4: Canvas and Workflows — Design Document

**Date:** 2026-02-27
**Status:** Approved
**Requirements:** WKFL-01–09
**Planned plans:** 04-01 through 04-05

---

## Goal

Users can build automation workflows on a React Flow canvas, compile them to LangGraph StateGraphs, run them manually or on a schedule, and interact with HITL approval nodes directly in the canvas. Two pre-built starter templates ship with the phase.

### Gate Criteria

1. User can drag nodes, connect edges, and save a workflow with `schema_version: "1.0"`
2. Workflow compiles to a `StateGraph` and executes end-to-end
3. Morning Digest template runs: fetch email → condition → summarize → send to Telegram
4. Alert template runs: webhook → keyword match → condition → create task → notify
5. HITL approval node pauses execution and shows Approve/Reject in the canvas
6. Cron-triggered workflow runs as job owner with full 3-gate ACL

---

## Architecture Decision

**Approach: Stateless compile-on-run + LangGraph AsyncPostgresSaver checkpointer**

Compile `definition_json` → `StateGraph` fresh on each run. Use LangGraph's built-in PostgreSQL checkpointer to persist graph state between steps (enabling HITL pause/resume). SSE pushes node-level status events to the canvas in real time.

Rejected alternatives:
- Compile-on-save + Redis state — stale compiled state risk, adds second state store for no measurable benefit at 100-user scale
- Compile-on-save + version hash — premature optimization (YAGNI)

---

## Section 1: Data Model

### `workflows`
```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
owner_user_id    UUID REFERENCES users(id) NOT NULL
name             VARCHAR(255) NOT NULL
description      TEXT
definition_json  JSONB NOT NULL          -- React Flow native: {schema_version, nodes, edges}
is_template      BOOLEAN DEFAULT FALSE   -- true = read-only starter template
template_source_id UUID REFERENCES workflows(id)  -- set when copied from a template
created_at       TIMESTAMPTZ DEFAULT now()
updated_at       TIMESTAMPTZ DEFAULT now()
```

### `workflow_runs`
```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
workflow_id      UUID REFERENCES workflows(id) NOT NULL
owner_user_id    UUID REFERENCES users(id) NOT NULL
trigger_type     VARCHAR(20) NOT NULL CHECK (trigger_type IN ('manual','cron','webhook'))
status           VARCHAR(20) NOT NULL CHECK (status IN ('pending','running','paused_hitl','completed','failed'))
checkpoint_id    VARCHAR(255)    -- LangGraph AsyncPostgresSaver thread_id
started_at       TIMESTAMPTZ DEFAULT now()
completed_at     TIMESTAMPTZ
result_json      JSONB
```

### `workflow_triggers`
```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
workflow_id      UUID REFERENCES workflows(id) NOT NULL
owner_user_id    UUID REFERENCES users(id) NOT NULL
trigger_type     VARCHAR(20) NOT NULL CHECK (trigger_type IN ('cron','webhook'))
cron_expression  VARCHAR(100)    -- for cron triggers (e.g. "0 8 * * 1-5")
webhook_secret   VARCHAR(255)    -- for webhook triggers
is_active        BOOLEAN DEFAULT TRUE
```

**LangGraph checkpointer:** `AsyncPostgresSaver` from `langgraph.checkpoint.postgres.aio` stores full graph state in the existing PostgreSQL instance. `checkpoint_id` in `workflow_runs` is the LangGraph `thread_id` used to resume a paused graph at HITL.

Templates are loaded via Alembic data migration (runs with `just migrate`). Template rows have `is_template=true`, `owner_user_id=null`.

---

## Section 2: Canvas Node Types

Six node types — no arbitrary `eval`, sandboxed expression evaluator for condition nodes:

| Node Type | Config Fields | Execution |
|---|---|---|
| `trigger_node` | `trigger_type` (cron/webhook), `cron_expression` | Entry point — wires graph inputs, no runtime handler |
| `agent_node` | `agent` (email/calendar/project), `instruction` | Invokes sub-agent |
| `tool_node` | `tool_name` (from tool_registry), `params` | Calls tool through 3-gate middleware |
| `condition_node` | `expression` (e.g. `output.count > 0`) | LangGraph conditional edge → `true`/`false` branch |
| `hitl_approval_node` | `message` (prompt shown to user) | LangGraph `interrupt()` — pauses graph |
| `channel_output_node` | `channel` (telegram/teams/web), `template` | Calls channel gateway |

**Condition expression evaluator** — sandboxed, supports only:
- Comparison: `>`, `<`, `==`, `!=`
- String: `contains`, `is_empty`, `not`
- Operand: `output.<field>` (previous node's structured output)

Each node carries a `status` field in its React Flow `data`: `idle | running | completed | failed | awaiting_approval`. Custom node renderers display a colored status ring. `hitl_approval_node` renders Approve/Reject buttons when status is `awaiting_approval`.

**Node type registry:** `backend/agents/node_handlers.py` maps `node_type → async handler(node_config, state, user_context)`. Adding a new node type requires one entry here.

---

## Section 3: Compiler Architecture

`compile_workflow_to_stategraph(definition_json, user_context)` in `backend/agents/graphs.py`:

```
1. Assert schema_version == "1.0"
2. Topological sort nodes via edges
3. For each node → look up handler in node_handlers registry
4. Build StateGraph:
   - Regular node      → add_node() + add_edge()
   - condition_node    → add_conditional_edges(true_branch, false_branch)
   - hitl_approval_node → add_node() with interrupt() inside handler
5. Set entry point from trigger_node
6. Compile with AsyncPostgresSaver(conn=db_connection, thread_id=run_id)
7. Return (compiled_graph, thread_id)
```

### WorkflowState TypedDict

```python
class WorkflowState(TypedDict):
    run_id: UUID
    user_context: UserContext
    node_outputs: dict[str, Any]   # keyed by node_id — accumulated across all nodes
    current_output: Any            # output of the last completed node
    hitl_result: str | None        # "approved" | "rejected" | None
```

`node_outputs` accumulates results so any node can reference a prior node's output by `node_id`, enabling non-linear data flow even in a mostly-linear graph. `WorkflowState` is separate from `BlitzState` — workflows are not conversations.

---

## Section 4: Execution & HITL Flow

### Manual Run
```
POST /api/workflows/{id}/run
→ create WorkflowRun (status=pending)
→ enqueue Celery task: execute_workflow(run_id)
→ return {run_id}

Frontend subscribes: GET /api/workflows/runs/{run_id}/events (SSE)
```

### Celery Worker Execution
```
1. Load WorkflowRun → get owner_user_id → build UserContext (3-gate ACL applies)
2. compile_workflow_to_stategraph(definition_json, user_context)
3. astream_events() → for each event push SSE:
   - {event: "node_started",    node_id}
   - {event: "node_completed",  node_id, output}
   - {event: "hitl_paused",     node_id, message}  → WorkflowRun.status = paused_hitl → STOP
   - {event: "workflow_completed", output}
   - {event: "workflow_failed",    error}
4. On completion → WorkflowRun.status = completed, store result_json
```

### HITL Resume
```
POST /api/workflows/runs/{run_id}/approve  (or /reject)
→ assert WorkflowRun.status == paused_hitl
→ resume graph from checkpoint_id with hitl_result = "approved" | "rejected"
→ execution continues from interrupt point
→ SSE events resume on same or new subscription
```

### Cron Trigger
```
Celery beat reads active WorkflowTriggers (trigger_type=cron)
→ fires execute_workflow(run_id) per cron_expression
→ same execution path as manual run
→ no active SSE: result stored in result_json
→ if HITL hit: status=paused_hitl → nav badge increments
  (frontend polls GET /api/workflows/runs/pending-hitl)
```

### Webhook Trigger
```
POST /api/webhooks/{webhook_id}   (public endpoint — no JWT)
→ validate X-Webhook-Secret header against WorkflowTrigger.webhook_secret
→ look up WorkflowTrigger → get owner_user_id
→ create WorkflowRun, enqueue Celery task
→ return 202 Accepted
```

---

## Section 5: API Surface

```
# Workflow CRUD (JWT required, 3-gate ACL)
GET    /api/workflows                          list user's workflows
POST   /api/workflows                          create workflow
GET    /api/workflows/{id}                     get workflow + definition_json
PUT    /api/workflows/{id}                     update definition_json
DELETE /api/workflows/{id}                     delete workflow

# Templates (JWT required)
GET    /api/workflows/templates                list starter templates
POST   /api/workflows/templates/{id}/copy      copy template → user-owned workflow

# Execution (JWT required)
POST   /api/workflows/{id}/run                 manual run → {run_id}
GET    /api/workflows/runs/{run_id}/events     SSE stream (node status events)
GET    /api/workflows/runs/{run_id}            get run status + result_json
POST   /api/workflows/runs/{run_id}/approve    HITL approve
POST   /api/workflows/runs/{run_id}/reject     HITL reject
GET    /api/workflows/runs/pending-hitl        count of paused_hitl runs (nav badge)

# Triggers (JWT required)
GET    /api/workflows/{id}/triggers            list triggers
POST   /api/workflows/{id}/triggers            create cron or webhook trigger
DELETE /api/workflows/{id}/triggers/{tid}      delete trigger

# Webhooks (public — X-Webhook-Secret header, no JWT)
POST   /api/webhooks/{webhook_id}              fire webhook trigger → 202 Accepted
```

---

## Section 6: Frontend Structure

```
frontend/src/
├── app/
│   ├── workflows/
│   │   ├── page.tsx                        ← workflow list + template gallery (Server Component)
│   │   └── [id]/page.tsx                   ← canvas editor page (Server Component shell)
│   └── api/workflows/
│       ├── route.ts                        ← proxy: GET/POST /api/workflows
│       ├── [id]/route.ts                   ← proxy: GET/PUT/DELETE
│       ├── [id]/run/route.ts               ← proxy: POST run
│       ├── runs/[run_id]/
│       │   ├── events/route.ts             ← SSE proxy (streams through)
│       │   ├── approve/route.ts
│       │   └── reject/route.ts
│       ├── runs/pending-hitl/route.ts
│       └── templates/
│           ├── route.ts
│           └── [id]/copy/route.ts
├── components/
│   └── canvas/
│       ├── workflow-canvas.tsx             ← React Flow wrapper (use client)
│       ├── node-palette.tsx                ← left sidebar drag source (use client)
│       ├── run-controls.tsx                ← Run button + status bar (use client)
│       └── nodes/
│           ├── trigger-node.tsx
│           ├── agent-node.tsx
│           ├── tool-node.tsx
│           ├── condition-node.tsx          ← two output handles: true / false
│           ├── hitl-approval-node.tsx      ← Approve/Reject buttons when awaiting_approval
│           └── channel-output-node.tsx
└── hooks/
    ├── use-workflow.ts                     ← CRUD operations
    ├── use-workflow-run.ts                 ← SSE subscription + Map<node_id, NodeStatus>
    └── use-pending-hitl.ts                ← polls pending-hitl count for nav badge
```

`use-workflow-run.ts` subscribes to the SSE stream and maintains a `Map<node_id, NodeStatus>` that `workflow-canvas.tsx` reads to update each node's visual state. When a `hitl_paused` event arrives, the specific node's status becomes `awaiting_approval`, which triggers inline Approve/Reject buttons in `hitl-approval-node.tsx`.

---

## Section 7: Pre-built Templates

Stored as JSON fixtures in `backend/data/workflow_templates/`. Loaded via Alembic data migration.

### Morning Digest (`morning_digest.json`)
```
trigger_node        cron: "0 8 * * 1-5"  (weekdays 8am)
    ↓
tool_node           fetch_email, last_24h
    ↓
condition_node      output.count > 0
    ↓ true                          ↓ false
agent_node          summarize        [end — no emails, workflow completes silently]
    ↓
channel_output_node telegram
```

### Alert (`alert.json`)
```
trigger_node        webhook
    ↓
tool_node           keyword_match, keywords=["URGENT","BLOCKER"]
    ↓
condition_node      output.matched == true
    ↓ true                          ↓ false
tool_node           create_task      [end — no match, workflow completes silently]
    ↓
channel_output_node telegram
```

Template API:
- `GET /api/workflows/templates` — returns both templates
- `POST /api/workflows/templates/{id}/copy` — clones `definition_json` into a new `workflows` row with requesting user's `owner_user_id` and `is_template=false`

---

## Implementation Plan (5 plans)

| Plan | Scope |
|---|---|
| 04-01 | React Flow canvas UI + node palette + workflow CRUD API + Alembic migration |
| 04-02 | Canvas-to-StateGraph compiler + WorkflowState + node handlers registry |
| 04-03 | Workflow triggers: cron (Celery beat) + webhook endpoint + SSE run events |
| 04-04 | HITL approval nodes: interrupt() + resume API + canvas status overlay |
| 04-05 | Pre-built templates: JSON fixtures + data migration + template gallery UI |

---

## Key Constraints

- `definition_json` always has `schema_version: "1.0"` — required for future migration safety (ADR-001, ADR-005)
- Celery workers run as job owner (`owner_user_id`) — full 3-gate ACL applies to scheduled runs
- `WorkflowState` is separate from `BlitzState` — workflows are not conversations
- Condition expression evaluator is sandboxed — no `eval`, no arbitrary code execution
- Webhook endpoint validates `X-Webhook-Secret` header — no JWT, but runs as trigger's `owner_user_id`
- No Kubernetes, no separate vector DB, no new infrastructure — Docker Compose only
