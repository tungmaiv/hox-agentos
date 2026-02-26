# Phase 3 Design: Sub-Agents, Memory & Integrations

**Date:** 2026-02-26
**Status:** Approved
**Author:** Brainstorming session

---

## 1. Goals & Success Criteria

Phase 3 makes the agent genuinely useful for daily work. At phase end, all of the following must be true:

1. User asks "summarize my unread emails" → email sub-agent returns structured summary
2. User asks "what's on my calendar today?" → calendar sub-agent returns schedule with conflict detection
3. User asks "status of Project X?" → project sub-agent queries CRM via MCP, returns structured result
4. Old conversations are summarized into episode summaries; user facts accumulate as long-term memory with semantic search across sessions
5. Agent responses include rich A2UI components (cards, tables) — not plain text

**Priority order (highest to lowest):**
1. Long-term memory with semantic search
2. MCP integration through all 3 security gates
3. A2UI rich responses
4. Email + calendar sub-agents (vehicles to validate the above)

---

## 2. Architecture Strategy

**Approach: Infrastructure-First, Sequential Waves**

Each wave produces a testable, independently verifiable layer. Wave N+1 does not start until Wave N passes its exit criterion.

```
Wave 1 — Memory Infrastructure (Celery + bge-m3 + pgvector)
Wave 2 — MCP Framework (HTTP+SSE client + CRM mock + security)
Wave 3 — Sub-Agents + A2UI (agents delegated from master, rich UI output)
```

Pre-wave: Settings Infrastructure (03-00) — shared scaffolding used by all waves.

---

## 3. Sub-Phase Plan

| Sub-phase | Name | Key Deliverables | Exit Criterion |
|-----------|------|-----------------|----------------|
| **03-00** | Settings Infrastructure | `system_config` table, Settings page shell, Agents + Integrations submenus (stubs) | Admin can toggle an agent on/off; settings page renders |
| **03-01** | Celery + Embedding Pipeline | `scheduler/celery_app.py`, `memory/embeddings.py` (bge-m3 via FlagEmbedding), `embed_and_store` Celery task, DB migrations for `memory_facts` + `memory_episodes` | Celery task embeds a test string; pgvector semantic search returns correct top result |
| **03-02** | Medium + Long-term Memory | `memory/medium_term.py` (episode summarization), `memory/long_term.py` (fact storage + semantic search), `_load_memory_node` updated to query pgvector | After 2 sessions, agent correctly recalls a fact stated in a previous conversation |
| **03-03** | MCP Framework + CRM Mock | `mcp/client.py` (HTTP+SSE), MCP tools wired into `gateway/tool_registry.py`, CRM mock server (`infra/mcp-crm/`), Settings → Integrations CRUD live | CRM tool call passes all 3 security gates, returns structured result; server appears in Settings → Integrations |
| **03-04** | Sub-Agents | `agents/subagents/email_agent.py`, `calendar_agent.py`, `project_agent.py`; master agent delegates; project agent uses MCP CRM tools | "What's on my calendar?" returns structured events; "status of Project X?" returns CRM data |
| **03-05** | A2UI Components | `CalendarCard`, `EmailSummaryCard`, `ProjectStatusWidget` frontend components; `A2UIMessageRenderer` integration | Rich card renders in chat for each agent type |

**Dependency order:**
```
03-00  (no dependencies — start immediately)
03-01  (no dependencies — start with 03-00)
03-02  depends on 03-01  (needs embedding pipeline)
03-03  depends on 03-00  (needs settings stub for Integrations page)
03-04  depends on 03-02 + 03-03  (needs memory + MCP)
03-05  depends on 03-04  (needs agents producing structured output)
```

---

## 4. Data Flow

### 4.1 Memory Flow

```
User message → master_agent.py
  ├── _load_memory_node:
  │     ├── fetch recent turns from memory_conversations (short-term, existing)
  │     └── semantic search memory_facts WHERE user_id = $1 (long-term, new)
  ├── LLM generates response
  └── _save_memory_node:
        ├── save turn to memory_conversations (existing)
        ├── dispatch Celery task: embed_and_store(text, user_id, type="fact")
        └── [non-blocking] Celery worker → bge-m3 → pgvector INSERT

After N turns (configurable, default 10):
  └── Celery task: summarize_episode(conversation_id, user_id)
        ├── blitz/summarizer LLM → episode summary text
        └── embed_and_store(summary, user_id, type="episode") → memory_episodes
```

### 4.2 MCP Tool Call Flow

```
Agent selects tool "crm.get_project_status"
  ├── Gate 1: JWT validated (security/jwt.py)
  ├── Gate 2: RBAC — user has "crm:read" permission (security/rbac.py)
  ├── Gate 3: ToolAcl table check (gateway/agui_middleware.py)
  ├── mcp/client.py → HTTP POST to mcp-crm service /sse endpoint
  ├── CRM mock → returns structured JSON result
  └── Agent receives result as tool output, continues reasoning
```

### 4.3 A2UI Response Flow

```
Sub-agent produces structured output (e.g., list[CalendarEvent])
  ├── Agent emits A2UI envelope in AG-UI stream
  ├── Frontend A2UIMessageRenderer detects envelope type
  └── Renders: CalendarCard | EmailSummaryCard | ProjectStatusWidget
```

---

## 5. Database Schema

### New Tables

```sql
-- Admin key/value config (agent feature flags, active embedding model name)
CREATE TABLE system_config (
    key        TEXT PRIMARY KEY,
    value      JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- MCP server registry (admin-managed via Settings → Integrations)
CREATE TABLE mcp_servers (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name       TEXT NOT NULL UNIQUE,
    url        TEXT NOT NULL,
    auth_token BYTEA,              -- AES-256 encrypted (same pattern as credentials table)
    is_active  BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Medium-term memory: episode summaries per user/conversation
CREATE TABLE memory_episodes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),
    conversation_id UUID NOT NULL,
    summary         TEXT NOT NULL,
    embedding       vector(1024),  -- nullable until Celery job runs
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Long-term memory: persistent facts per user
CREATE TABLE memory_facts (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id),
    content    TEXT NOT NULL,
    source     TEXT,               -- "conversation" | "user_stated" | "inferred"
    embedding  vector(1024),       -- nullable until Celery job runs
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### Indexes

```sql
-- HNSW for fast approximate nearest neighbor semantic search
CREATE INDEX ON memory_facts    USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;
CREATE INDEX ON memory_episodes USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;

-- Memory isolation enforcement
CREATE INDEX ON memory_facts    (user_id);
CREATE INDEX ON memory_episodes (user_id, conversation_id);
```

**Critical constraint:** Every memory query includes `WHERE user_id = $1` sourced from JWT — never from request body.

---

## 6. Extensibility Design

### 6.1 Embedding Model — Pluggable in Code, No Settings UI

The pgvector `vector(1024)` dimension is locked. Changing the model requires a full reindex migration — not a safe runtime toggle.

**Design:** `memory/embeddings.py` exposes an `EmbeddingProvider` protocol. Phase 3 ships one concrete implementation: `BGE_M3Provider`. Future model swaps are code changes + Alembic migration, not UI config.

The active model name is stored in `system_config` (`key="embedding_model"`) for admin visibility only — no toggle UI.

```python
class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dimension(self) -> int: ...
```

### 6.2 MCP Servers — Admin Settings UI (Settings → Integrations)

MCP servers are registered in the `mcp_servers` table. Admin UI provides:
- List all servers with status (connected / unreachable)
- Add new server (name, URL, auth token)
- Delete server

MCP tools discovered from each server are re-registered in `gateway/tool_registry.py` on server add/edit.

### 6.3 Agent Management — Enable/Disable Toggle (Settings → Agents)

Agents in Phase 3 are code-defined (LangGraph). The Settings → Agents submenu provides admin-controlled feature flags stored in `system_config`.

- Toggle: enable/disable each sub-agent (email, calendar, project)
- Master agent checks `system_config` before delegating to a sub-agent
- Full agent authoring deferred to Phase 4 (Canvas)

---

## 7. New Directory Structure

```
backend/
├── scheduler/
│   ├── celery_app.py          ← Celery app + Redis broker
│   └── tasks/
│       ├── __init__.py
│       └── embedding.py       ← embed_and_store(), summarize_episode()
├── memory/
│   ├── short_term.py          ← existing
│   ├── embeddings.py          ← EmbeddingProvider protocol + BGE_M3Provider
│   ├── medium_term.py         ← episode summarization + storage
│   └── long_term.py           ← fact storage + pgvector semantic search
├── mcp/
│   ├── client.py              ← HTTP+SSE MCP client
│   └── registry.py            ← discover + register MCP tools
└── agents/
    └── subagents/
        ├── email_agent.py
        ├── calendar_agent.py
        └── project_agent.py

infra/
└── mcp-crm/                   ← mock CRM MCP server (FastAPI, /sse endpoint)

frontend/src/
├── app/settings/
│   ├── agents/page.tsx        ← Settings → Agents (enable/disable toggles)
│   └── integrations/page.tsx  ← Settings → Integrations (MCP CRUD)
└── components/a2ui/
    ├── CalendarCard.tsx
    ├── EmailSummaryCard.tsx
    └── ProjectStatusWidget.tsx
```

---

## 8. Architecture Invariants (Unchanged)

These Phase 2 invariants carry forward unchanged into Phase 3:

- All tool calls (including MCP tools) pass all 3 security gates in order
- Memory queries always parameterized: `WHERE user_id = $1` from JWT
- All LLM calls via `get_llm()` → LiteLLM Proxy (never direct SDK imports)
- Celery workers run as job owner's UserContext — no privilege escalation
- No separate vector DB — pgvector in existing PostgreSQL only
- Credentials never passed to LLMs, never logged, never returned to frontend

---

## 9. Known Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| bge-m3 model download size (~570MB) | Download at Docker build time; cache in image layer |
| bge-m3 CPU load blocking Celery worker | Set `--concurrency=2` for embedding worker; separate queue from other tasks |
| A2UI Public Preview (v0.8) breaking changes | Pin version; test upgrade in isolation before phase starts |
| `CREDENTIAL_ENCRYPTION_KEY` missing in .env | Fail fast on startup if key absent; document in `.dev-secrets.example` |
| MCP server unreachable at runtime | Health check on server add; graceful degradation (tool returns structured error) |

---

## 10. Not in Scope (Phase 3)

- WhatsApp / Telegram channel sub-agent (Phase 4)
- Canvas workflow authoring (Phase 4)
- Full agent authoring UI (Phase 4)
- Switching embedding models via UI (post-MVP)
- Real Gmail / Google Calendar OAuth flows (Phase 3 uses mock data; OAuth wiring is Phase 4)
- Kubernetes, connection pooling, horizontal scaling (post-MVP)
