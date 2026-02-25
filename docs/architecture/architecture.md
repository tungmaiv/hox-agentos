# Blitz AgentOS — Comprehensive Architecture Document

> **Version:** 1.0
> **Date:** 2026-02-24
> **Status:** Approved
> **Scope:** MVP (On-Premise, ~100 Users)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Business Goals & Constraints](#2-business-goals--constraints)
3. [System Architecture Overview](#3-system-architecture-overview)
4. [Technology Stack](#4-technology-stack)
5. [Frontend Architecture](#5-frontend-architecture)
6. [Security Runtime](#6-security-runtime)
7. [Agent Orchestration](#7-agent-orchestration)
8. [Memory Subsystem](#8-memory-subsystem)
9. [LLM Provider Layer](#9-llm-provider-layer)
10. [Backend Tools & Sandbox](#10-backend-tools--sandbox)
11. [MCP Integration](#11-mcp-integration)
12. [Scheduler Subsystem](#12-scheduler-subsystem)
13. [Channel Integration](#13-channel-integration)
14. [Credential Management](#14-credential-management)
15. [Audit Logging & Observability](#15-audit-logging--observability)
16. [Infrastructure & Deployment](#16-infrastructure--deployment)
17. [Data Models](#17-data-models)
18. [Architecture Decision Records](#18-architecture-decision-records)
19. [Implementation Roadmap](#19-implementation-roadmap)
20. [Open Risks & Mitigations](#20-open-risks--mitigations)

---

## 1. Project Overview

**Blitz AgentOS** is an enterprise-grade, on-premise Agentic Operating System built for Blitz employees (~100 users). It provides a unified platform to automate daily workflows, orchestrate multi-step business processes via a low-code canvas, connect to internal systems via MCP, and interact through multiple channels (web, Telegram, WhatsApp, MS Teams).

The system is inspired by OpenClaw's architecture — local-first, multi-agent, sandboxed — extended with enterprise security (Keycloak SSO, RBAC/ACL), multi-tenant memory isolation, and a pluggable multi-channel delivery layer.

**Core value proposition:**
- Replace manual daily routines (email digest, calendar summaries, project status) with autonomous agents
- Let non-technical users build workflows via a visual canvas without writing code
- Enforce enterprise security guarantees: no credential leakage to LLMs, per-user memory isolation, per-tool ACL

---

## 2. Business Goals & Constraints

### 2.1 Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| F1 | Low-code canvas for visual workflow creation | High |
| F2 | Master agent with specialized sub-agents (email, calendar, project, channel) | High |
| F3 | Three-tier hierarchical memory with per-user isolation | High |
| F4 | Cron-based autonomous job scheduler | High |
| F5 | Web chat with AG-UI streaming and A2UI generative widgets | High |
| F6 | Multi-channel delivery: web, Telegram, WhatsApp, MS Teams | Medium |
| F7 | MCP integration to internal systems (CRM, docs) | Medium |
| F8 | Docker sandbox for unsafe code/shell execution | Medium |
| F9 | Human-in-the-loop (HITL) approval nodes in workflows | Medium |

### 2.2 Non-Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR1 | Keycloak SSO + RBAC + per-tool ACL on every call | Critical |
| NFR2 | On-premise deployment (Docker Compose → Kubernetes) | Critical |
| NFR3 | Per-user memory isolation — no cross-user data reads ever | Critical |
| NFR4 | Credentials never visible to LLM, frontend, or logs | Critical |
| NFR5 | Extensible channel adapter pattern — add new channels without touching agent code | High |
| NFR6 | Structured audit log for every tool invocation (who, what, when, allowed/denied) | High |
| NFR7 | Chat first-token latency < 3 seconds for local LLM | Medium |
| NFR8 | Pluggable LLM providers (on-premise + cloud fallback) | High |
| NFR9 | Vietnamese language support in memory search | High |

### 2.3 Constraints

- **On-premise only** — no SaaS dependencies for data processing; external LLM APIs optional/fallback
- **~100 users** — design for this scale; avoid over-engineering for millions of users
- **Docker Compose for MVP** — Kubernetes migration deferred to post-MVP
- **PostgreSQL as sole database** — no additional vector databases; use pgvector extension

---

## 3. System Architecture Overview

Blitz AgentOS is organized into five horizontal layers communicating top-down:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         LAYER 1: FRONTEND                                │
│  Next.js + CopilotKit  │  React Flow Canvas  │  AG-UI Chat  │  A2UI UI  │
└──────────────────────────────┬───────────────────────────────────────────┘
                               │ HTTPS + AG-UI / REST (JWT attached)
┌──────────────────────────────▼───────────────────────────────────────────┐
│                    LAYER 2: SECURITY RUNTIME                             │
│  FastAPI Copilot Runtime  │  Keycloak JWT  │  RBAC  │  Tool ACL         │
└──────────────────────────────┬───────────────────────────────────────────┘
                               │ Authenticated internal calls
┌──────────────────────────────▼───────────────────────────────────────────┐
│                    LAYER 3: AGENT ORCHESTRATION                          │
│  LangGraph Master Agent  │  Sub-Agents  │  Workflow StateGraph Engine    │
└────────┬─────────────────┬─────────────────┬────────────────────────────┘
         │                 │                 │
┌────────▼──────┐  ┌───────▼──────┐  ┌──────▼──────────────────────────────┐
│  LAYER 4a:    │  │  LAYER 4b:   │  │  LAYER 4c:                          │
│  TOOLS &      │  │  MEMORY      │  │  LLM GATEWAY                        │
│  SANDBOX      │  │  SUBSYSTEM   │  │  LiteLLM Proxy                      │
│  Docker exec  │  │  PostgreSQL  │  │  Ollama / OpenAI / Claude / Kimi    │
└───────────────┘  │  + pgvector  │  └─────────────────────────────────────┘
                   └──────────────┘
┌──────────────────────────────────────────────────────────────────────────┐
│                    LAYER 5: INFRASTRUCTURE                               │
│  PostgreSQL+pgvector │ Redis │ Keycloak │ Celery │ Channel Gateway       │
│  MCP Servers (HTTP+SSE) │ Audit Logs │ Docker Sandbox Runtime            │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Project Directory Layout

```
blitz-agentos/
├── docker-compose.yml          # Dev orchestration
├── .env                        # Shared secrets (never committed)
├── backend/                    # FastAPI + LangGraph orchestrator
├── frontend/                   # Next.js + CopilotKit
├── infra/
│   ├── keycloak/               # Realm config, client exports
│   ├── postgres/               # Init SQL, migrations
│   ├── redis/                  # Redis config
│   ├── sandbox-runtime/        # Docker-in-Docker base images
│   ├── litellm/                # LiteLLM proxy config
│   ├── ollama/                 # Local LLM model config
│   ├── mcp-crm/                # CRM MCP server
│   ├── mcp-docs/               # Docs MCP server
│   └── alloy/                  # Grafana Alloy (future log shipping)
├── channel-gateways/
│   ├── telegram/               # Telegram inbound webhook service
│   ├── whatsapp/               # WhatsApp sidecar (Node.js)
│   └── teams/                  # MS Teams Bot Framework service
├── logs/
│   └── blitz/                  # JSON audit log files (volume mounted)
└── docs/
    ├── architecture/           # This document
    ├── design/                 # Original design docs
    ├── implementation/         # Implementation guide
    └── research/               # Research papers
```

---

## 4. Technology Stack

### 4.1 Locked Technology Decisions

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| Frontend framework | Next.js | 15+ | SSR, App Router, API routes for AG-UI proxy |
| Agent UI protocol | CopilotKit (AG-UI) | Latest | Streaming, tool call visualization, HITL |
| Generative UI | A2UI / CopilotKit | Latest | LLM-driven widget rendering (cards, forms, tables) |
| Canvas library | **React Flow (Xyflow) v12** | 12+ | Node/edge JSON = `definition_json` directly; MIT core |
| Backend framework | FastAPI | 0.115+ | Async, Pydantic native, AG-UI compatible |
| Agent orchestration | LangGraph | 0.2+ | StateGraph, Deep Agents, HITL, checkpointer |
| Data validation | PydanticAI | Latest | Tool I/O schemas, type-safe agent state |
| Identity | Keycloak | 26+ | OIDC/JWT, RBAC, enterprise SSO |
| Primary database | PostgreSQL | 16+ | ACID, pgvector, JSONB for workflow definitions |
| Vector search | pgvector | 0.8+ | Embedded in PostgreSQL; no separate vector DB |
| **Embedding model** | **bge-m3 (BAAI)** | Latest | 1024-dim, multilingual (Vietnamese), self-hosted |
| Task queue | Celery | 5+ | Distributed task execution, cron scheduling |
| Cache / broker | Redis | 7+ | Celery broker, session cache, rate limiting |
| **LLM gateway** | **LiteLLM Proxy** | Latest | Unified endpoint for all LLM providers |
| Local LLM | Ollama | Latest | On-premise LLM serving (Qwen2.5, Llama3 etc.) |
| Cloud LLM (primary) | Anthropic Claude | claude-sonnet-4-6 | Fallback / high-quality tasks |
| Cloud LLM (coding) | Kimi via OpenRouter | kimi-k1.5 | Coding-specific tasks |
| Cloud LLM (general) | OpenAI | gpt-4o | Fallback general tasks |
| MCP transport | **HTTP + SSE** | MCP spec | Standard MCP protocol; each server is a Docker service |
| Sandbox execution | Docker SDK | Latest | Per-request container isolation |
| **Audit logging** | **structlog → JSON files** | Latest | Loki-ready; Grafana Alloy ships to Loki at production |
| Future observability | Grafana + Prometheus + Loki | - | Add before production; file logs already compatible |

---

## 5. Frontend Architecture

### 5.1 Directory Structure

```
frontend/
├── next.config.js
└── src/
    ├── app/
    │   ├── layout.tsx                    # CopilotKit provider, Keycloak session
    │   ├── page.tsx                      # Main app entry
    │   └── api/
    │       └── copilotkit/route.ts       # AG-UI proxy → FastAPI runtime
    ├── components/
    │   ├── canvas/
    │   │   ├── CanvasRoot.tsx            # React Flow root, node/edge state
    │   │   ├── NodePalette.tsx           # Draggable node types sidebar
    │   │   ├── NodeRenderer.tsx          # Custom node renderers per type
    │   │   └── nodes/
    │   │       ├── AgentNode.tsx         # Sub-agent node
    │   │       ├── ToolNode.tsx          # Backend tool node
    │   │       ├── MCPNode.tsx           # MCP tool node
    │   │       └── HITLNode.tsx          # Human-in-the-loop approval node
    │   ├── chat/
    │   │   ├── ChatPanel.tsx             # AG-UI chat container
    │   │   ├── MessageList.tsx           # Message history with streaming
    │   │   └── InputBar.tsx             # User input + send
    │   └── a2ui/
    │       ├── A2UIMessageRenderer.tsx   # Parses A2UI JSONL envelopes
    │       └── widgets/
    │           ├── Card.tsx              # Summary card widget
    │           ├── Table.tsx             # Data table widget
    │           ├── Form.tsx              # Input form / approval dialog
    │           └── Progress.tsx          # Step progress indicator
    ├── hooks/
    │   ├── use-copilot-provider.ts       # CopilotKit + Keycloak JWT injection
    │   ├── use-frontend-tools.ts         # useFrontendTool: addNode, updateNode, deleteNode
    │   ├── use-acl.ts                    # Frontend tool visibility per user role
    │   └── use-co-agent.ts              # useCoAgent: canvas ↔ backend StateGraph sync
    └── lib/
        ├── types.ts                      # Shared TypeScript types
        └── a2ui-spec.ts                  # A2UI JSONL envelope type definitions
```

### 5.2 Canvas JSON Schema (Workflow Definition)

The React Flow state IS the `Workflow.definition_json`. This schema is versioned and must remain stable.

```typescript
// lib/types.ts
interface WorkflowDefinition {
  schema_version: "1.0";           // MUST increment on breaking changes
  entry_node: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

type NodeType = "agent" | "tool" | "mcp" | "hitl";

interface WorkflowNode {
  id: string;
  type: NodeType;
  position: { x: number; y: number };
  data: {
    label: string;
    // type-specific config:
    agentType?: string;            // "email_agent" | "calendar_agent" | ...
    toolName?: string;             // "email.fetch" | "calendar.list" | ...
    mcpServer?: string;            // "crm" | "docs"
    mcpTool?: string;              // "search_leads" | ...
    hitlPrompt?: string;           // Approval question shown to user
  };
}

interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  condition?: "success" | "failure" | "always";
}
```

### 5.3 AG-UI + A2UI Protocol

- **AG-UI**: CopilotKit's streaming protocol between frontend and FastAPI runtime. Handles token streaming, tool call visualization, and `renderAndWait` for HITL.
- **A2UI**: Structured JSONL envelopes emitted by agents in their response text. The `A2UIMessageRenderer` parses these and renders React widgets instead of raw text.

```
Agent emits in message body:
  {"type":"surfaceUpdate","surface":"card","data":{"title":"Morning Digest","items":[...]}}
  {"type":"dataModelUpdate","key":"approval_required","value":true}

A2UIMessageRenderer parses JSONL lines → renders <Card />, <Form /> etc.
```

---

## 6. Security Runtime

### 6.1 Three-Layer Security Model

Every request passes through three sequential security gates:

```
Incoming Request
      │
      ▼
┌─────────────────────────────────────────────────┐
│ Gate 1: JWT Validation (security/jwt.py)         │
│ - Verify Keycloak JWT signature (JWKS)           │
│ - Check expiry, issuer, audience                 │
│ - Extract user_id, email, roles → TokenClaims    │
└──────────────────────┬──────────────────────────┘
                       │ TokenClaims
                       ▼
┌─────────────────────────────────────────────────┐
│ Gate 2: RBAC Permission Check (security/rbac.py) │
│ - Map Keycloak roles → internal Permissions      │
│ - has_permission(user, "tool:email.read")        │
│ - Deny if role doesn't grant required permission │
└──────────────────────┬──────────────────────────┘
                       │ Authorized UserContext
                       ▼
┌─────────────────────────────────────────────────┐
│ Gate 3: Tool ACL (gateway/agui_middleware.py)    │
│ - On TOOLCALL_START event: read tool_name        │
│ - Query ToolAcl table for (tool, user_roles)     │
│ - Deny with 403 AG-UI error if not in allow_roles│
│ - Covers both backend tools AND MCP tools        │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
                  Agent / Tool Execution
```

### 6.2 Module Breakdown

```
backend/security/
├── keycloak_client.py    # Fetch + cache JWKS; optional introspection endpoint
├── jwt.py                # decode_token(token) → TokenClaims; verify sig/exp/iss/aud
├── rbac.py               # Map Keycloak roles → Permissions; has_permission()
├── acl.py                # check_acl(user, tool_name) → bool; queries ToolAcl table
└── deps.py               # FastAPI dependencies: get_current_user(), require_permission()

backend/gateway/
├── runtime.py            # Copilot Runtime init; AG-UI ↔ LangGraph binding
├── agui_middleware.py    # TOOLCALL_START interceptor: runs Gate 3 ACL check
└── tool_registry.py      # Central registry: name, description, required_permissions,
                          #   sandbox_required, mcp_server, mcp_tool
```

### 6.3 Authentication Flow

```
1. User opens Blitz AgentOS web app
2. Redirect to Keycloak login (OIDC Authorization Code flow)
3. User authenticates with Keycloak (SSO, MFA if configured)
4. Keycloak issues JWT (access token + refresh token)
5. Frontend stores JWT in memory (not localStorage — XSS protection)
6. All AG-UI + REST requests attach JWT in Authorization header
7. FastAPI extracts JWT → validates → injects UserContext into request state
8. All downstream tool calls receive UserContext (never the raw JWT)
```

---

## 7. Agent Orchestration

### 7.1 Directory Structure

```
backend/agents/
├── master_agent.py           # run_conversation(), run_workflow() entrypoints
├── graphs.py                 # compile_workflow_to_stategraph(definition_json)
├── state/
│   ├── __init__.py
│   └── types.py              # BlitzState TypedDict shared across all nodes
└── subagents/
    ├── email_agent.py        # Email read/draft/summarize workflows
    ├── calendar_agent.py     # Schedule analysis, event creation, agenda
    ├── project_agent.py      # Task management, status updates via MCP
    └── channel_agent.py      # Multi-channel message routing decisions
```

### 7.2 Master Agent (LangGraph Deep Agent)

The master agent is a LangGraph Deep Agent with three middleware layers:

```python
# agents/master_agent.py

# Middleware stack (OpenClaw-style):
# 1. Filesystem middleware: read_file, write_file, ls, search (for temp context)
# 2. Todo middleware: forces explicit multi-step planning before acting
# 3. Sub-agent middleware: spawn isolated sub-agent loops for domain tasks

async def run_conversation(user_context: UserContext, message: str, channel: str):
    """Handles real-time chat via AG-UI."""
    # 1. Load short-term memory (last N turns)
    # 2. Run memory_search for relevant long-term facts
    # 3. Invoke master agent; may delegate to sub-agents
    # 4. Stream response via AG-UI; emit A2UI envelopes for structured output

async def run_workflow(workflow_id: UUID, params: dict, user_context: UserContext):
    """Executes a saved canvas workflow (called by scheduler or manual trigger)."""
    # 1. Load Workflow.definition_json from DB
    # 2. Compile to StateGraph via graphs.compile_workflow_to_stategraph()
    # 3. Execute with PostgreSQL checkpointer (for HITL durability)
    # 4. Persist WorkflowRun; deliver result via channel dispatcher
```

### 7.3 Shared State

```python
# agents/state/types.py
from typing import TypedDict, Any

class BlitzState(TypedDict):
    user_id: str
    conversation_id: str
    channel: str                  # "web" | "telegram" | "whatsapp" | "ms_teams"
    context: dict                 # user roles, preferences, current task
    messages: list[dict]          # conversation history (short-term)
    last_output: Any              # last node output
    todo_list: list[str]          # master agent's explicit plan steps
    hitl_pending: bool            # True when paused at HITL node
```

### 7.4 Workflow Compilation

```python
# agents/graphs.py

def compile_workflow_to_stategraph(definition: WorkflowDefinition) -> StateGraph:
    graph = StateGraph(BlitzState)

    node_builders = {
        "agent":  _build_agent_node,    # wraps sub-agent invocation
        "tool":   _build_tool_node,     # wraps backend tool call (ACL already checked)
        "mcp":    _build_mcp_node,      # wraps MCPClient.call_tool()
        "hitl":   _build_hitl_node,     # renderAndWait → pauses execution
    }

    for node in definition["nodes"]:
        builder = node_builders[node["type"]]
        graph.add_node(node["id"], builder(node["data"]))

    for edge in definition["edges"]:
        if edge.get("condition"):
            graph.add_conditional_edges(
                edge["source"],
                lambda state, c=edge["condition"]: c,
                {edge["condition"]: edge["target"]}
            )
        else:
            graph.add_edge(edge["source"], edge["target"])

    graph.set_entry_point(definition["entry_node"])

    # PostgreSQL checkpointer: survives backend restarts during HITL pauses
    checkpointer = PostgresSaver.from_conn_string(settings.database_url)
    return graph.compile(checkpointer=checkpointer)
```

### 7.5 Sub-Agent Pattern

Each sub-agent is a self-contained LangGraph agent with its own tools and memory scope:

```python
# agents/subagents/email_agent.py
def create_email_agent(user_context: UserContext) -> CompiledGraph:
    tools = [
        fetch_emails,      # tools/email_tools.py
        send_email,
        draft_reply,
    ]
    # Uses user_context.user_id for all credential lookups — never tokens
    return create_react_agent(get_llm("blitz/master"), tools)
```

---

## 8. Memory Subsystem

### 8.1 Three-Tier Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│  Tier 1: Short-Term (memory_conversations)                         │
│  Raw verbatim conversation turns, per user + conversation_id       │
│  Used to: maintain session continuity                              │
│  Pruning: last N turns injected into prompt; older turns archived  │
├────────────────────────────────────────────────────────────────────┤
│  Tier 2: Medium-Term / Episodic (memory_episodes)                  │
│  LLM-generated summaries of completed sessions and tasks           │
│  Used to: compress history without losing important context        │
│  Trigger: token threshold OR session boundary                      │
├────────────────────────────────────────────────────────────────────┤
│  Tier 3: Long-Term / Facts (memory_facts + pgvector)               │
│  Stable facts, user preferences, project knowledge                 │
│  Embedding: bge-m3 (1024-dim), cosine similarity search            │
│  Used to: inject relevant knowledge into any agent prompt          │
└────────────────────────────────────────────────────────────────────┘
```

### 8.2 PostgreSQL Schema

```sql
-- Tier 1: Short-term verbatim turns
CREATE TABLE memory_conversations (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID NOT NULL REFERENCES users(id),
  conversation_id  UUID NOT NULL,
  role             TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  channel          TEXT NOT NULL,  -- "web", "telegram", "whatsapp", "ms_teams"
  content          TEXT NOT NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_mem_conv ON memory_conversations (user_id, conversation_id, created_at DESC);

-- Tier 2: Medium-term episodic summaries
CREATE TABLE memory_episodes (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID NOT NULL REFERENCES users(id),
  workspace_id     UUID,
  conversation_id  UUID,
  title            TEXT,
  summary          TEXT NOT NULL,
  tags             TEXT[],
  started_at       TIMESTAMPTZ,
  ended_at         TIMESTAMPTZ,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_mem_episodes ON memory_episodes (user_id, started_at DESC);

-- Tier 3: Long-term facts + vector search
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE memory_facts (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID NOT NULL REFERENCES users(id),
  workspace_id     UUID,
  scope            TEXT NOT NULL,   -- "user_profile" | "project" | "org"
  subject          TEXT NOT NULL,   -- "project:CRM-1234", "user:preferred_language"
  title            TEXT,
  content          TEXT NOT NULL,
  tags             TEXT[],
  embedding        vector(1024),    -- bge-m3 dimension; DO NOT change without reindex
  provider         TEXT NOT NULL DEFAULT 'local',  -- "local" | "openai"
  model            TEXT NOT NULL DEFAULT 'BAAI/bge-m3',
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_mem_facts_user ON memory_facts (user_id, scope, subject);
-- IVFFlat: tune lists = sqrt(expected_row_count); start with 100
CREATE INDEX idx_mem_facts_vec ON memory_facts
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Optional: file-based memory (OpenClaw-style project files)
CREATE TABLE memory_files (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES users(id),
  workspace_id UUID,
  path         TEXT NOT NULL,
  size_bytes   BIGINT,
  mtime        TIMESTAMPTZ,
  hash         TEXT,               -- SHA256 for dirty-bit tracking
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE memory_chunks (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  file_id      UUID NOT NULL REFERENCES memory_files(id) ON DELETE CASCADE,
  user_id      UUID NOT NULL,
  workspace_id UUID,
  start_line   INT,
  end_line     INT,
  content      TEXT NOT NULL,
  embedding    vector(1024),
  provider     TEXT,
  model        TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_mem_chunks_vec ON memory_chunks
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### 8.3 Embedding Service

```
backend/memory/
├── short_term.py      # append_turn(), get_recent_turns(n)
├── medium_term.py     # create_episode(), get_recent_episodes()
├── long_term.py       # write_fact(), memory_search()
├── summarizer.py      # LLM-based: summarize_turns() → episode summary
├── embeddings.py      # EmbeddingService: FlagModel(bge-m3), hash-based cache
└── indexer.py         # Celery tasks: embed_fact(id), embed_chunk(id)
```

**Embedding service** (`memory/embeddings.py`):
```python
from FlagEmbedding import FlagModel

class EmbeddingService:
    _model: FlagModel | None = None

    @classmethod
    def get_model(cls) -> FlagModel:
        if cls._model is None:
            cls._model = FlagModel('BAAI/bge-m3', use_fp16=True)
        return cls._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.get_model().encode(texts, batch_size=12).tolist()
```

**Memory search tool** (vector similarity + metadata filter):
```sql
-- memory/long_term.py → memory_search()
SELECT id, subject, title, content, scope, tags
FROM memory_facts
WHERE user_id = $user_id
  AND (workspace_id = $workspace_id OR workspace_id IS NULL)
  AND (scope = ANY($scopes) OR $scopes IS NULL)
ORDER BY embedding <-> $query_embedding   -- cosine distance
LIMIT $limit;
```

### 8.4 Security Invariant

**All memory queries are parameterized on `user_id` from the JWT, never from user input.** There is no API parameter to override the user_id — it is always extracted from the validated token.

```python
# Every memory function signature enforces this pattern:
async def get_recent_turns(
    user_id: UUID,          # ← always from get_current_user(), never from request body
    conversation_id: UUID,
    n: int = 20
) -> list[Turn]:
    ...
```

---

## 9. LLM Provider Layer

### 9.1 LiteLLM Proxy Architecture

All LLM calls in Blitz AgentOS go through a **self-hosted LiteLLM Proxy**. No agent or tool code references provider-specific SDKs directly.

```
LangGraph Agents
     │
     │ OpenAI-compatible API calls
     ▼
LiteLLM Proxy (port 4000)
     │
     ├──► Ollama (local) ──► Qwen2.5:72b, Llama3.3:70b, etc.
     ├──► Anthropic ──────► claude-sonnet-4-6 (fallback/quality)
     ├──► OpenAI ──────────► gpt-4o-mini (fast/cheap tasks)
     └──► OpenRouter ──────► Kimi k1.5 (coding tasks)
```

### 9.2 Model Aliases

Agent code uses stable aliases, never provider-specific model names:

| Alias | Use Case | Primary | Fallback |
|-------|----------|---------|---------|
| `blitz/master` | Master agent, complex reasoning | Ollama/Qwen2.5:72b | Claude Sonnet 4.6 |
| `blitz/fast` | Simple sub-tasks, classification | Ollama/Llama3.2:3b | OpenAI gpt-4o-mini |
| `blitz/coder` | Code generation, debugging | OpenRouter/Kimi k1.5 | Claude Sonnet 4.6 |
| `blitz/embedder` | Not via LiteLLM — direct bge-m3 | Local FlagModel | — |
| `blitz/summarizer` | Memory summarization | Ollama/Llama3.2:3b | OpenAI gpt-4o-mini |

### 9.3 LiteLLM Configuration

```yaml
# infra/litellm/config.yaml
model_list:
  # Master agent — prefer local, fall back to Claude
  - model_name: blitz/master
    litellm_params:
      model: ollama/qwen2.5:72b
      api_base: http://ollama:11434
  - model_name: blitz/master
    litellm_params:
      model: anthropic/claude-sonnet-4-6
      api_key: os.environ/ANTHROPIC_KEY

  # Fast tasks — prefer local small model
  - model_name: blitz/fast
    litellm_params:
      model: ollama/llama3.2:3b
      api_base: http://ollama:11434
  - model_name: blitz/fast
    litellm_params:
      model: openai/gpt-4o-mini
      api_key: os.environ/OPENAI_KEY

  # Coding tasks — Kimi via OpenRouter
  - model_name: blitz/coder
    litellm_params:
      model: openrouter/moonshotai/kimi-k1.5
      api_key: os.environ/OPENROUTER_KEY
  - model_name: blitz/coder
    litellm_params:
      model: anthropic/claude-sonnet-4-6
      api_key: os.environ/ANTHROPIC_KEY

router_settings:
  routing_strategy: least-busy
  fallbacks:
    - {"blitz/master": ["anthropic/claude-sonnet-4-6"]}
    - {"blitz/fast": ["openai/gpt-4o-mini"]}
    - {"blitz/coder": ["anthropic/claude-sonnet-4-6"]}
  retry_after: 5
  num_retries: 3

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  database_url: os.environ/DATABASE_URL   # for usage tracking
```

### 9.4 Agent Integration

```python
# core/config.py — single source of truth for LLM access
def get_llm(alias: str = "blitz/master") -> ChatOpenAI:
    return ChatOpenAI(
        model=alias,
        base_url=settings.litellm_url,   # http://litellm:4000
        api_key=settings.litellm_key,
        streaming=True,
    )
```

---

## 10. Backend Tools & Sandbox

### 10.1 Tool Structure

```
backend/tools/
├── __init__.py
├── email_tools.py        # fetch_emails, send_email, draft_reply
├── calendar_tools.py     # list_events, summarize_day, create_event
├── project_tools.py      # create_task, update_status, list_tasks
├── dataops_tools.py      # safe DB queries, CSV export, analytics
├── memory_tools.py       # memory_search, write_fact, get_episodes
├── mcp_tools.py          # Generic MCP wrapper: mcp_call(server, tool, params)
└── sandbox_tools.py      # bash_exec, python_exec — routed to Docker sandbox
```

### 10.2 Tool Registration

Every tool is registered in `gateway/tool_registry.py` with security metadata:

```python
# gateway/tool_registry.py
TOOL_REGISTRY: dict[str, ToolMeta] = {
    "email.fetch": ToolMeta(
        fn=fetch_emails,
        description="Fetch user emails since a given timestamp",
        required_permissions=["tool:email.read"],
        sandbox_required=False,
    ),
    "bash.exec": ToolMeta(
        fn=bash_exec,
        description="Execute a bash command in an isolated container",
        required_permissions=["tool:sandbox.exec"],
        sandbox_required=True,
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

### 10.3 Docker Sandbox

High-risk tools (`sandbox_required=True`) execute in ephemeral Docker containers, never on the host:

```
backend/sandbox/
├── docker_client.py    # Docker SDK wrapper: create, exec, destroy container
├── policies.py         # Allowlist/denylist; base image selection per tool type
└── executor.py         # Orchestrates: check policy → create → exec → capture → destroy
```

**Execution lifecycle:**
```
1. executor.run(tool_job) called
2. Check policies.py: is this tool allowed? which base image?
3. docker_client.create_container(image, limits={cpu: "0.5", mem: "256m", network: "none"})
4. docker_client.exec(container, command)
5. Capture stdout/stderr with timeout
6. docker_client.destroy(container)     ← always runs, even on error
7. Return ExecutionResult(stdout, stderr, exit_code)
```

**Base images** (minimal, lean):
- `blitz-sandbox-common`: Python 3.12, common libs, no network
- `blitz-sandbox-browser`: Playwright, for web automation tasks

---

## 11. MCP Integration

### 11.1 Transport: HTTP + SSE (MCP Standard)

All MCP servers use the standard MCP HTTP+SSE transport. Each server is an independent Docker service.

```
backend/mcp/
├── client.py              # MCPClient: list_tools(), call_tool()
└── servers/
    ├── crm_server.py      # Internal CRM MCP server (FastMCP)
    └── docs_server.py     # Document store MCP server (FastMCP)
```

### 11.2 MCP Server Implementation

```python
# mcp/servers/crm_server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("crm-server")

@mcp.tool()
def search_leads(query: str, user_id: str, limit: int = 10) -> list[dict]:
    """Search CRM leads by query. user_id enforces data scoping."""
    # Credentials for CRM loaded from environment, NOT from params
    ...

@mcp.tool()
def get_contact(contact_id: str, user_id: str) -> dict:
    """Get a CRM contact by ID."""
    ...

# Run: uvicorn crm_server:mcp.sse_app --port 8001
```

### 11.3 MCP Client

```python
# mcp/client.py
from mcp import ClientSession
from mcp.client.sse import sse_client

class MCPClient:
    def __init__(self, servers: dict[str, str]):
        # servers = {"crm": "http://mcp-crm:8001/sse", "docs": "http://mcp-docs:8002/sse"}
        self.servers = servers

    async def call_tool(self, server: str, tool: str, params: dict) -> dict:
        url = self.servers[server]
        async with sse_client(url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool, params)
                return result.content
```

### 11.4 ACL for MCP Tools

MCP tools are registered in `tool_registry` and pass through the same Gate 3 ACL check as backend tools. There is no separate security perimeter for MCP.

---

## 12. Scheduler Subsystem

### 12.1 Architecture

```
backend/scheduler/
├── celery_app.py     # Celery + Redis broker config; task: run_scheduled_job(job_id)
├── jobs.py           # Cron parsing, next_run_at computation, enqueue_due_jobs()
└── worker.py         # Celery task implementation: load job → compile workflow → run
```

### 12.2 Execution Flow

```
1. User creates ScheduledJob via POST /api/scheduler/jobs
   (cron: "0 8 * * MON-FRI", workflow_id, delivery_channel: "telegram")

2. Celery Beat: every minute, calls enqueue_due_jobs()
   - SELECT jobs WHERE next_run_at <= now() AND enabled = true
   - Enqueue run_scheduled_job(job_id) task for each

3. Celery Worker executes run_scheduled_job(job_id):
   a. Load ScheduledJob + Workflow from DB
   b. Build UserContext (user_id, roles) — scheduler runs AS the job owner
   c. Compile Workflow.definition_json → LangGraph StateGraph
   d. master_agent.run_workflow(workflow_id, params, user_context)
   e. Persist WorkflowRun (status, started_at, finished_at, state_snapshot)
   f. Update job.last_run_at, job.next_run_at
   g. channel_dispatcher.send_message(user_id, delivery_channel, result)

4. Failure handling:
   - Celery retry with exponential backoff (max 3 retries)
   - WorkflowRun.status = "failed" + error_message after final failure
   - Alert via web notification (A2UI) that scheduled job failed
```

### 12.3 Security Note

The Celery worker runs scheduled jobs **with the original job owner's UserContext**, not as a privileged service account. This means:
- Memory is accessed as that user
- Tool ACL checks use that user's roles
- No privilege escalation via scheduled jobs

---

## 13. Channel Integration

### 13.1 Architecture: Pluggable Adapter Pattern

```
External Platform
      │
      │ webhook / SDK event
      ▼
┌─────────────────────────────────────────────────────────────┐
│            Channel Gateway (FastAPI module)                  │
│                                                             │
│  handle_inbound(InternalMessage)                            │
│  ├── _enrich_identity()   → resolve to Blitz user_id       │
│  ├── _check_pairing()     → enforce connection allowlist    │
│  └── _route_to_agent()    → POST /api/agents/chat          │
│                                                             │
│  send_outbound(InternalMessage)                             │
│  └── adapters[channel].send(msg)                           │
│                                                             │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌─────────┐ │
│  │ Telegram   │ │ WhatsApp   │ │ MS Teams   │ │ [Future]│ │
│  │ Adapter    │ │ Adapter    │ │ Adapter    │ │ Adapter │ │
│  └────────────┘ └────────────┘ └────────────┘ └─────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 13.2 Canonical Message Model

```python
# channels/models.py
class ChannelType(str, Enum):
    telegram = "telegram"
    whatsapp = "whatsapp"
    ms_teams = "ms_teams"
    slack = "slack"
    web = "web"
    # Add new values here to add new channels

class InternalMessage(BaseModel):
    direction: Literal["inbound", "outbound"]
    channel: ChannelType
    external_user_id: str         # Telegram chat_id / phone number / Teams user id
    external_chat_id: str | None  # Group/channel/thread id
    user_id: UUID | None          # Blitz user_id (populated after identity resolution)
    conversation_id: UUID | None  # AG-UI thread (populated after session lookup)
    text: str | None
    attachments: list[dict] = []
    is_group: bool = False
    metadata: dict = {}           # Platform-specific raw payload for debugging
```

### 13.3 Adding a New Channel

To add Discord, Zalo, Line, or any future channel:

1. Add value to `ChannelType` enum
2. Implement `ChannelAdapter` protocol (one class with `send()` method)
3. Create inbound webhook route OR small sidecar service
4. Register adapter in `ChannelGateway` constructor
5. Add config section in `core/config.py`

**No changes needed to:** agent code, tool code, memory subsystem, or security layer.

### 13.4 Channel Security

- Inbound webhooks from external platforms authenticate via **HMAC signature** (Telegram uses token in URL; WhatsApp uses `X-Hub-Signature-256`; Teams uses Bot Framework auth)
- Outbound calls from agents to channels go through the dispatcher — agents never call platform APIs directly
- External channels receive **final replies only** — streaming chunks stay in the web UI

---

## 14. Credential Management

### 14.1 Core Security Invariant

```
LLM prompt   → sees: user_id, task parameters
Frontend     → sees: tool results (structured data), never tokens
Audit logs   → log: user_id, tool name, timestamp — NEVER tokens
DB (encrypted) → stores: access_token (encrypted), refresh_token (encrypted)
Backend tool → resolves: credentials internally from DB using user_id from JWT
```

### 14.2 OAuth Delegated Flow (Gmail / O365)

```sql
CREATE TABLE user_credentials (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        UUID NOT NULL REFERENCES users(id),
  provider       TEXT NOT NULL,          -- "gmail", "o365", "z_ai"
  account_id     TEXT NOT NULL,          -- email address or account identifier
  access_token   TEXT NOT NULL,          -- AES-256 encrypted, KMS key
  refresh_token  TEXT,                   -- AES-256 encrypted, KMS key
  expires_at     TIMESTAMPTZ,
  scopes         TEXT[],                 -- granted OAuth scopes
  created_at     TIMESTAMPTZ DEFAULT now(),
  updated_at     TIMESTAMPTZ DEFAULT now(),
  UNIQUE (user_id, provider, account_id)
);
```

**Token usage in tools** (the only correct pattern):
```python
@tool
def fetch_emails(input: FetchEmailsInput) -> list[EmailSummary]:
    user_ctx = get_user_context()                      # from JWT, injected by FastAPI
    creds = credentials_repo.get(user_ctx.user_id, "gmail")  # DB lookup, decrypted in memory
    if creds.expires_at < datetime.utcnow():
        creds = credentials_repo.refresh(creds)        # auto-refresh, update DB
    client = GmailClient(access_token=creds.access_token)
    return client.fetch(since=input.since)
    # creds.access_token is never logged, never returned to LLM
```

### 14.3 Internal Systems (Service Account / Keycloak Assertion)

For internal systems that trust Keycloak (CRM, internal mail, HR system):

```python
# No credential DB needed — backend asserts user identity via Keycloak JWT
async def call_internal_crm(user_id: str, query: str) -> dict:
    # Generate short-lived signed assertion token
    assertion = keycloak_client.create_user_assertion(user_id, ttl=60)
    response = await httpx.post(
        settings.crm_api_url + "/search",
        headers={"Authorization": f"Bearer {assertion}"},
        json={"query": query, "user_id": user_id}
    )
    return response.json()
```

---

## 15. Audit Logging & Observability

### 15.1 Audit Log Architecture

**MVP:** Structured JSON files on disk, log rotation, Loki-compatible format.
**Production:** Grafana Alloy tails files → Loki; Prometheus for metrics; Grafana dashboards.

```
backend/core/logging.py     ← structlog setup, audit_log helper
logs/blitz/
├── audit.jsonl             ← tool invocations (rotates daily)
├── agent.jsonl             ← agent decisions, sub-agent calls
├── memory.jsonl            ← memory reads/writes
└── scheduler.jsonl         ← job executions, failures
```

### 15.2 Audit Log Schema

Every log line is a valid JSON object (JSONL format):

```json
{
  "timestamp": "2026-02-24T08:00:00.123Z",
  "level": "info",
  "event": "tool_call",
  "user_id": "a1b2c3d4-...",
  "session_id": "e5f6...",
  "tool": "email.fetch",
  "allowed": true,
  "duration_ms": 142.3,
  "acl_roles_matched": ["employee"],
  "channel": "web"
}

{
  "timestamp": "2026-02-24T08:01:00.000Z",
  "level": "warning",
  "event": "tool_call_denied",
  "user_id": "b2c3d4e5-...",
  "tool": "bash.exec",
  "allowed": false,
  "reason": "acl_denied",
  "user_roles": ["employee"],
  "required_roles": ["admin", "developer"]
}
```

### 15.3 Logging Setup

```python
# core/logging.py
import structlog
from logging.handlers import TimedRotatingFileHandler

def configure_logging():
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.CallsiteParameterAdder(
                [structlog.processors.CallsiteParameter.MODULE]
            ),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
    )

# Separate file handlers per log category
def get_audit_logger() -> structlog.BoundLogger:
    handler = TimedRotatingFileHandler(
        "/var/log/blitz/audit.jsonl",
        when="midnight", backupCount=30
    )
    return structlog.get_logger("audit").bind()
```

### 15.4 Future Grafana Stack (Pre-Production)

Add to `docker-compose.yml` before production:

```yaml
# infra: Prometheus + Grafana + Loki + Alloy
prometheus:
  image: prom/prometheus:latest
  volumes: ["./infra/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml"]

grafana:
  image: grafana/grafana:latest
  ports: ["3001:3000"]

loki:
  image: grafana/loki:latest

alloy:
  image: grafana/alloy:latest
  volumes:
    - "./infra/alloy/config.alloy:/etc/alloy/config.alloy"
    - "./logs:/var/log/blitz"   # ← same volume mount as backend
```

```hcl
# infra/alloy/config.alloy
loki.source.file "blitz_audit" {
  targets = [
    {__path__ = "/var/log/blitz/audit.jsonl",     job = "audit"},
    {__path__ = "/var/log/blitz/agent.jsonl",     job = "agent"},
    {__path__ = "/var/log/blitz/scheduler.jsonl", job = "scheduler"},
  ]
  forward_to = [loki.write.default.receiver]
}
```

---

## 16. Infrastructure & Deployment

### 16.1 Docker Compose Services

```yaml
# docker-compose.yml (MVP)
services:
  # ── Identity ────────────────────────────────
  keycloak:
    image: quay.io/keycloak/keycloak:26
    ports: ["8080:8080"]
    environment:
      KEYCLOAK_ADMIN: admin
      KEYCLOAK_ADMIN_PASSWORD: ${KEYCLOAK_ADMIN_PASSWORD}

  # ── Storage ─────────────────────────────────
  postgres:
    image: pgvector/pgvector:pg16
    volumes: ["postgres_data:/var/lib/postgresql/data"]
    environment:
      POSTGRES_DB: blitz
      POSTGRES_USER: blitz
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}

  redis:
    image: redis:7-alpine
    volumes: ["redis_data:/data"]

  # ── LLM Gateway ─────────────────────────────
  ollama:
    image: ollama/ollama:latest
    volumes: ["ollama_data:/root/.ollama"]
    deploy:
      resources:
        reservations:
          devices: [{capabilities: [gpu]}]  # optional GPU

  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    depends_on: [ollama]
    volumes: ["./infra/litellm/config.yaml:/app/config.yaml"]
    command: ["--config", "/app/config.yaml"]
    ports: ["4000:4000"]
    environment:
      ANTHROPIC_KEY: ${ANTHROPIC_KEY}
      OPENAI_KEY: ${OPENAI_KEY}
      OPENROUTER_KEY: ${OPENROUTER_KEY}

  # ── MCP Servers ─────────────────────────────
  mcp-crm:
    build: ./infra/mcp-crm
    ports: ["8001:8001"]
    environment:
      CRM_DB_URL: ${CRM_DB_URL}

  mcp-docs:
    build: ./infra/mcp-docs
    ports: ["8002:8002"]

  # ── Backend ─────────────────────────────────
  backend:
    build: ./backend
    depends_on: [postgres, redis, keycloak, litellm]
    volumes: ["./logs:/var/log/blitz"]
    environment:
      DATABASE_URL: postgresql://blitz:${POSTGRES_PASSWORD}@postgres/blitz
      REDIS_URL: redis://redis:6379
      KEYCLOAK_URL: http://keycloak:8080
      LITELLM_URL: http://litellm:4000
      MCP_CRM_URL: http://mcp-crm:8001/sse
      MCP_DOCS_URL: http://mcp-docs:8002/sse

  celery-worker:
    build: ./backend
    command: celery -A scheduler.celery_app worker --concurrency=4
    depends_on: [redis, postgres, litellm]
    volumes: ["./logs:/var/log/blitz"]

  celery-beat:
    build: ./backend
    command: celery -A scheduler.celery_app beat --loglevel=info
    depends_on: [redis, postgres]

  # ── Frontend ────────────────────────────────
  frontend:
    build: ./frontend
    depends_on: [backend]
    ports: ["3000:3000"]
    environment:
      NEXT_PUBLIC_BACKEND_URL: http://backend:8000
      NEXT_PUBLIC_KEYCLOAK_URL: http://keycloak:8080

  # ── Channel Gateways ────────────────────────
  channel-telegram:
    build: ./channel-gateways/telegram
    environment:
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      BACKEND_URL: http://backend:8000

  channel-whatsapp:
    build: ./channel-gateways/whatsapp
    environment:
      BACKEND_URL: http://backend:8000

volumes:
  postgres_data:
  redis_data:
  ollama_data:
```

### 16.2 Port Map

| Service | Port | Protocol |
|---------|------|----------|
| Frontend (Next.js) | 3000 | HTTPS |
| Backend (FastAPI) | 8000 | HTTPS |
| Keycloak | 8080 | HTTPS |
| LiteLLM Proxy | 4000 | HTTP (internal) |
| MCP CRM Server | 8001 | HTTP+SSE (internal) |
| MCP Docs Server | 8002 | HTTP+SSE (internal) |
| Ollama | 11434 | HTTP (internal) |
| Grafana (future) | 3001 | HTTPS |

### 16.3 Kubernetes Migration Path (Post-MVP)

Each Docker Compose service maps directly to a Kubernetes Deployment + Service. Priority order for migration:
1. Backend + Celery workers (horizontal scaling for concurrent users)
2. Frontend (CDN + multiple replicas)
3. LiteLLM Proxy (scale with backend)
4. Ollama (GPU node pool, resource requests/limits)
5. PostgreSQL → managed PostgreSQL (PgBouncer for connection pooling)

---

## 17. Data Models

### 17.1 Core Models Summary

```
backend/core/models/
├── user.py        # User (keycloak_id, email, display_name)
├── acl.py         # Role, Permission, RolePermission, UserRole, ToolAcl
├── workflow.py    # Workflow (definition_json), WorkflowRun (state_snapshot)
├── job.py         # ScheduledJob (cron, workflow_id, delivery_channel)
├── memory.py      # ShortTermMemory, MediumTermMemory/Episodes, LongTermFact
├── channel.py     # ChannelAccount (user ↔ platform mapping), ChannelSession
├── mcp.py         # MCPServer config (name, url, enabled)
└── credentials.py # UserCredentials (encrypted OAuth tokens per provider)
```

### 17.2 Key Relationships

```
User (1) ──── (N) ChannelAccount ──── (N) ChannelSession
User (1) ──── (N) Workflow ──── (N) WorkflowRun
User (1) ──── (N) ScheduledJob ──── FK──► Workflow
User (1) ──── (N) UserRole ──── (N) Role ──── (N) Permission
User (1) ──── (N) UserCredentials (per provider)
User (1) ──── (N) memory_conversations
User (1) ──── (N) memory_episodes
User (1) ──── (N) memory_facts
ToolAcl (N) ─ tool_name → checked against Role names
```

---

## 18. Architecture Decision Records

### ADR-001: Agent Orchestration — LangGraph + PydanticAI

**Status:** Accepted
**Decision:** Use LangGraph for stateful agent orchestration; PydanticAI for tool I/O validation
**Rationale:** LangGraph StateGraph maps directly to the canvas workflow model. HITL (`renderAndWait`) is native. PostgreSQL checkpointer enables durable HITL pauses across backend restarts. PydanticAI provides strict type-safe tool schemas aligned with NFR4 (no credential leakage).
**Consequence:** Canvas `definition_json` schema must be versioned (`schema_version` field). Breaking node schema changes require migration scripts.

---

### ADR-002: Memory Store — PostgreSQL + pgvector (no separate vector DB)

**Status:** Accepted
**Decision:** Use pgvector extension within the existing PostgreSQL instance
**Rationale:** 100-user scale doesn't justify operational complexity of a separate vector DB (Qdrant, Weaviate). Critical security advantage: memory isolation (`WHERE user_id = $1`) is enforced in the same SQL query as vector search, eliminating a class of cross-tenant data leak bugs. Single DB = simpler backup/restore.
**Consequence:** `embedding` column is `vector(1024)` — dimension locked to bge-m3. Changing embedding model requires a full reindex. IVFFlat index must be rebuilt when row count grows significantly.

---

### ADR-003: Embedding Model — bge-m3

**Status:** Accepted
**Decision:** Use `BAAI/bge-m3` as the sole embedding model, self-hosted via FlagEmbedding
**Rationale:** Multilingual (Vietnamese + English), 1024-dim (higher quality than 384-dim alternatives), 8192-token context window accommodates long documents, can run on CPU (no GPU required for MVP).
**Consequence:** Each `memory_facts` and `memory_chunks` row stores a `vector(1024)`. Run embedding in a dedicated Celery worker pool to avoid blocking the FastAPI event loop (CPU-bound operation).

---

### ADR-004: LLM Abstraction — LiteLLM Proxy

**Status:** Accepted
**Decision:** All LLM calls route through a self-hosted LiteLLM Proxy; agents use stable model aliases
**Rationale:** Multiple providers required (local Ollama, OpenAI, Anthropic, Kimi via OpenRouter, Z.AI). LiteLLM provides unified OpenAI-compatible API, automatic fallback routing, cost tracking, and retry logic. Swapping providers requires only config changes, no agent code changes.
**Consequence:** LiteLLM Proxy is a critical path service — it must be highly available before backend can start. Set health check dependency in Docker Compose.

---

### ADR-005: Canvas Frontend — React Flow (Xyflow) v12

**Status:** Accepted
**Decision:** Use React Flow v12 for the low-code canvas
**Rationale:** Purpose-built for node-based workflow editors. Its native `nodes` + `edges` JSON data model is exactly `Workflow.definition_json` — no translation layer needed. `useNodesState` / `useEdgesState` integrate directly with `useCoAgent` for backend StateGraph sync. TypeScript native, MIT core license, active community.
**Consequence:** `definition_json` schema is React Flow-compatible. Node `type` field maps to both React Flow custom node renderers AND `compile_workflow_to_stategraph` node builders.

---

### ADR-006: MCP Transport — HTTP + SSE

**Status:** Accepted
**Decision:** All MCP servers use MCP standard HTTP+SSE transport
**Rationale:** Standard MCP spec transport; no custom protocol needed. Each server is an independent Docker service discoverable by URL config. Tools in `tool_registry` reference `mcp_server` by name, resolved to URL at runtime.
**Consequence:** MCP server URLs must be configured in `core/config.py` as `mcp_servers: dict[str, str]`. All MCP servers must expose `/sse` endpoint.

---

### ADR-007: Audit Logging — structlog JSON Files → Grafana/Loki

**Status:** Accepted
**Decision:** MVP uses structured JSON file logging (structlog + TimedRotatingFileHandler); Grafana Alloy added pre-production to ship logs to Loki
**Rationale:** File-based logging is simple, zero infrastructure overhead for MVP. JSON JSONL format is natively Loki-compatible — no code changes needed when switching to Loki, only Alloy config addition.
**Consequence:** Backend and Celery workers must mount the `./logs` volume. Log files must never contain credential values (access tokens, refresh tokens, passwords).

---

### ADR-008: Credential Storage — Encrypted DB Table

**Status:** Accepted
**Decision:** Store OAuth credentials in `user_credentials` table with AES-256 column encryption; KMS key for encryption key management
**Rationale:** On-premise deployment means no managed secret store (AWS Secrets Manager) available. DB column encryption with application-level KMS is the pragmatic choice. HashiCorp Vault deferred to post-MVP as optional upgrade path.
**Consequence:** The application must never log credential values. The DB user for the credential service must be separate from the general application DB user. Rotate KMS key periodically.

---

## 19. Implementation Roadmap

| Phase | Goal | Key Deliverables | Dependencies |
|-------|------|-----------------|--------------|
| **Phase 1** | Identity & Skeleton | Keycloak + Postgres + Redis; FastAPI JWT middleware; Next.js + CopilotKit; basic `/api/agents/chat` | None |
| **Phase 2** | Agents, Tools & Memory | Master agent + 4 sub-agents; backend tools + Pydantic schemas; 3-tier memory with per-user isolation; LiteLLM integration; bge-m3 embedding service | Phase 1 |
| **Phase 3** | Canvas & Workflows | React Flow canvas; `compile_workflow_to_stategraph`; HITL nodes; A2UI renderer + widgets; workflow CRUD API; Postgres checkpointer | Phase 2 |
| **Phase 4** | Scheduler & Channels | Celery cron scheduler; Telegram gateway (MVP channel); channel gateway + adapter pattern; channel account identity resolution | Phase 2 |
| **Phase 5** | Hardening & Sandboxing | Docker sandbox for unsafe tools; ACL middleware (Gate 3); audit logging; MCP ACL; credential management; WhatsApp + Teams adapters | Phase 3 + 4 |
| **Phase 6** | Observability | Grafana + Prometheus + Loki + Alloy; performance tuning; load testing | Phase 5 |

### Phase Gate Criteria

Before starting each phase, the following must pass from the previous phase:

- **Phase 2 gate:** JWT validated, `/api/agents/chat` returns 200, Keycloak SSO working
- **Phase 3 gate:** All tool schemas tested, memory cross-user isolation verified, agent responds
- **Phase 4 gate:** Canvas workflow persists and runs a 2-node workflow end-to-end
- **Phase 5 gate:** Scheduled job creates WorkflowRun, Telegram delivers agent response
- **Phase 6 gate:** Docker sandbox runs without host access, 403 returned for ACL-denied tools

---

## 20. Open Risks & Mitigations

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| R1 | **Canvas schema instability** — changing `definition_json` node schema breaks existing saved workflows | High | Version field (`schema_version: "1.0"`) in every workflow. Write migration scripts for breaking changes. Gate new node types behind schema version bump. |
| R2 | **LangGraph HITL durability** — backend restart loses workflow state during HITL pause | High | PostgreSQL checkpointer stores state after every node. WorkflowRun.state_snapshot as backup. Celery task resumes from checkpoint on retry. |
| R3 | **pgvector IVFFlat performance degradation** — index accuracy drops as row count grows | Medium | Monitor `SELECT COUNT(*) FROM memory_facts` monthly. Rebuild index when count × 2 vs. initial. Target: `lists = sqrt(count)`. |
| R4 | **bge-m3 embedding dimension lock-in** — changing to a different model requires full reindex | Medium | Store `provider` + `model` per row. Write `reindex_all_facts()` Celery task. Accept downtime during reindex for MVP scale. |
| R5 | **LiteLLM Proxy single point of failure** — if proxy goes down, all LLM calls fail | Medium | Health check in Docker Compose (`depends_on: litellm: condition: service_healthy`). In Kubernetes: 2+ replicas with readiness probe. |
| R6 | **WhatsApp sidecar (Node.js)** — introduces second language runtime | Low | Define sidecar's internal API as OpenAPI spec. Keep sidecar thin (webhook → `POST /channels/whatsapp/incoming` only). No business logic in sidecar. |
| R7 | **Audit log credential leakage** — developer accidentally logs token in tool code | Low | Lint rule: ban `access_token` and `refresh_token` as log field keys. Code review checklist item. CI grep for credential keywords in log calls. |
| R8 | **Celery job failure silent** — scheduled job fails but user not notified | Low | `WorkflowRun.status = "failed"` record. Web notification via A2UI push. Admin dashboard shows failed jobs. Celery dead letter queue inspection. |

---

*Document maintained by: Architecture Team*
*Next review: Before Phase 3 kickoff (validate canvas schema stability)*
