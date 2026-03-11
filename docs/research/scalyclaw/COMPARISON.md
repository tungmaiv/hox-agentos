# Comparative Analysis: ScalyClaw vs OpenClaw vs AgentOS

> **Date:** March 2026  
> **Purpose:** Architecture comparison and lessons learned for Blitz AgentOS

---

## Executive Summary

This document compares three AI assistant platforms to inform the design of **Blitz AgentOS**:

| Platform | Type | Scale | Architecture Philosophy |
|----------|------|-------|------------------------|
| **ScalyClaw** | Open-source AI platform | Small teams (~10-100 users) | Horizontally scalable, worker-based |
| **OpenClaw** | Open-source personal assistant | Single user | Local-first, personal device |
| **AgentOS** | Enterprise Agentic OS (planned) | Enterprise (~100 users) | Enterprise security, multi-tenant |

**Key Finding:** AgentOS should combine OpenClaw's elegant local-first design with ScalyClaw's scalability patterns, while adding enterprise-grade security and multi-tenancy.

---

## Detailed Comparison Matrix

### 1. Architecture & Scale

| Aspect | ScalyClaw | OpenClaw | AgentOS (Proposed) |
|--------|-----------|----------|-------------------|
| **Primary Scale** | Small teams (10-100) | Personal (1 user) | Enterprise (~100 users) |
| **Process Model** | Node + Workers (scalable) | Single Gateway process | Multi-service (backend + workers) |
| **Scalability** | Horizontal (add workers) | Vertical (single node) | Horizontal (Celery workers) |
| **State Management** | Redis + SQLite | SQLite (local) | PostgreSQL + Redis |
| **Deployment** | Self-hosted, Docker | Local install, Docker | On-premise Docker Compose |

**Analysis:**
- OpenClaw's single-process simplicity is elegant for personal use but doesn't scale
- ScalyClaw's Node-Worker split is similar to AgentOS's Backend-Celery design
- AgentOS adds PostgreSQL for ACID guarantees and multi-user data isolation

### 2. Technology Stack

| Layer | ScalyClaw | OpenClaw | AgentOS |
|-------|-----------|----------|---------|
| **Runtime** | Bun | Node.js | Python (FastAPI) + Node.js (frontend) |
| **Frontend** | React 19 + Vite 6 | SvelteKit (Control UI) | Next.js 15 + React Flow |
| **Agent Framework** | Custom | Pi Agent (RPC) | LangGraph + PydanticAI |
| **Queue System** | BullMQ + Redis | In-process | Celery + Redis |
| **Database** | SQLite + sqlite-vec | SQLite + sqlite-vec | PostgreSQL + pgvector |
| **LLM Gateway** | OpenAI-compatible | Direct providers | LiteLLM Proxy |
| **Channels** | 7+ platforms | 20+ platforms | 4 platforms (MVP) |
| **Sandbox** | Unknown | Docker | Docker (planned) |

**Analysis:**
- **Bun vs Node vs Python:** AgentOS uses Python for better ML ecosystem (LangGraph, PydanticAI)
- **SQLite vs PostgreSQL:** PostgreSQL required for concurrent multi-user access
- **LangGraph:** Provides StateGraph and checkpointing that ScalyClaw/OpenClaw lack

### 3. Security Model

| Feature | ScalyClaw | OpenClaw | AgentOS |
|---------|-----------|----------|---------|
| **Authentication** | Token-based | Token-based | Keycloak SSO (OIDC) |
| **Authorization** | Skill permissions | Session-based | RBAC + Tool ACL |
| **Sandbox** | Unknown | Docker with allowlist | Docker + policies |
| **Guards** | 4 layers (echo, content, skill, command) | Basic command filtering | ACL + guards (planned) |
| **Secret Storage** | Vault (Redis-encrypted) | Environment variables | AES-256 encrypted DB |
| **Credential Leakage** | Never to LLM/logs | Never to LLM/logs | Never to LLM/logs/frontend |

**ScalyClaw's 4-Layer Guards:**
1. **Echo Guard:** Detects prompt injection via text repetition
2. **Content Guard:** Blocks harmful content (LLM-based)
3. **Skill & Agent Guard:** Audits code for malicious patterns
4. **Command Shield:** Blocks dangerous shell commands

**AgentOS Security Improvements:**
- Gate 1: JWT validation (Keycloak)
- Gate 2: RBAC permission check
- Gate 3: Tool ACL check
- Additional: Docker sandbox for unsafe operations

### 4. Memory System

| Aspect | ScalyClaw | OpenClaw | AgentOS |
|--------|-----------|----------|---------|
| **Storage** | SQLite + sqlite-vec + FTS5 | SQLite + sqlite-vec + FTS5 | PostgreSQL + pgvector |
| **Search** | Hybrid (vector + full-text) | Hybrid (vector + full-text) | Hybrid (vector + full-text) |
| **Extraction** | Auto-extract from conversations | Auto-extract from conversations | Auto-extract with bge-m3 |
| **Types** | Facts, preferences, events, relationships | Facts, preferences, entities | Facts, episodes, verbatim |
| **Isolation** | Per-conversation | Per-workspace | Per-user (strict) |

**OpenClaw Memory Features:**
- Episodic summaries
- Fact extraction
- File-based memory (AGENTS.md, SOUL.md, USER.md)
- Entity tracking

**AgentOS 3-Tier Memory:**
1. **Short-term:** Verbatim conversation turns
2. **Medium-term:** LLM-generated episode summaries
3. **Long-term:** Facts with bge-m3 embeddings (1024-dim)

### 5. Skills/Tools System

| Feature | ScalyClaw | OpenClaw | AgentOS |
|---------|-----------|----------|---------|
| **Language Support** | JS, Python, Rust, Bash | Node.js, TypeScript | Python (tools), MCP |
| **Hot Reload** | Yes (via Redis pub/sub) | Yes (file watcher) | Yes (planned) |
| **Deployment** | Zip archives | File-based | MCP servers + registry |
| **Dependencies** | Auto-install on first run | npm/pnpm | Containerized |
| **Scope** | Skill-specific permissions | Full tool access | ACL per tool |

**ScalyClaw Skill Structure:**
```
skills/
├── weather/
│   ├── SKILL.md      # Manifest
│   └── main.py       # Entry point
```

**AgentOS Tool Structure:**
```python
# gateway/tool_registry.py
TOOL_REGISTRY = {
    "email.fetch": ToolMeta(
        fn=fetch_emails,
        required_permissions=["tool:email.read"],
        sandbox_required=False,
    ),
}
```

### 6. Agent Orchestration

| Aspect | ScalyClaw | OpenClaw | AgentOS |
|--------|-----------|----------|---------|
| **Master Agent** | Custom orchestrator | Pi Agent (RPC) | LangGraph Deep Agent |
| **Sub-agents** | BullMQ queue-based | Session-based | LangGraph sub-graphs |
| **Delegation** | Agent queue | Session tools | LangGraph nodes |
| **State Machine** | Basic | None explicit | StateGraph with checkpointing |
| **HITL** | Unknown | Yes (renderAndWait) | Yes (CopilotKit) |
| **Workflows** | Unknown | Limited | Canvas-based StateGraph |

**Key Difference:**
- ScalyClaw/OpenClaw use message passing between agents
- AgentOS uses LangGraph's StateGraph for explicit state management
- AgentOS adds visual canvas for workflow creation

### 7. Channels

| Platform | ScalyClaw | OpenClaw | AgentOS |
|----------|-----------|----------|---------|
| **Discord** | ✓ | ✓ | Planned |
| **Telegram** | ✓ | ✓ | ✓ |
| **Slack** | ✓ | ✓ | Planned |
| **WhatsApp** | ✓ | ✓ | ✓ |
| **Signal** | ✓ | ✓ | - |
| **Teams** | ✓ | ✓ | ✓ |
| **iMessage** | - | ✓ (BlueBubbles) | - |
| **Web** | ✓ | ✓ (WebChat) | ✓ |
| **20+ others** | - | ✓ | - |

**Channel Architecture Comparison:**
- **ScalyClaw:** Channel adapters in Node, normalized message format
- **OpenClaw:** Gateway WebSocket network, unified control plane
- **AgentOS:** Pluggable adapter pattern in FastAPI, canonical InternalMessage

### 8. MCP Integration

| Feature | ScalyClaw | OpenClaw | AgentOS |
|---------|-----------|----------|---------|
| **Protocol** | MCP (stdio, HTTP, SSE) | Custom skills | MCP (HTTP+SSE) |
| **Auto-discovery** | Yes | N/A (file-based) | Yes |
| **Dashboard Config** | Yes | No | Yes |
| **Hot Reload** | Yes | N/A | Yes |
| **Tool ACL** | Unknown | No | Yes (Gate 3) |

**AgentOS MCP Design:**
- Separate MCP servers as Docker services
- Unified ACL check for all tools (backend + MCP)
- HTTP+SSE transport following MCP spec

---

## Lessons Learned for AgentOS

### From ScalyClaw

#### ✅ Adopt
1. **Horizontal Worker Scaling**
   - ScalyClaw's Node-Worker split validates AgentOS's Backend-Celery design
   - Workers share nothing except queue (Redis)

2. **Hot-Reload Architecture**
   - Skills, agents, config reload via Redis pub/sub
   - Zero-downtime updates

3. **4-Layer Security Guards**
   - Echo, content, skill, command guards
   - Fail-closed design principle

4. **Budget Control**
   - Per-model cost tracking
   - Monthly/daily limits with alerts

5. **Unified Channel Memory**
   - One mind across all channels
   - Cross-channel context retention

#### ⚠️ Adapt
1. **SQLite → PostgreSQL**
   - SQLite not suitable for concurrent multi-user access
   - PostgreSQL provides ACID + row-level security foundation

2. **Bun → Python**
   - Python has better ML/agent ecosystem
   - LangGraph, PydanticAI, FastAPI are Python-native

3. **Single Redis → Redis Cluster (Future)**
   - Redis is SPOF in ScalyClaw
   - AgentOS should plan for Redis Sentinel/Cluster

#### ❌ Avoid
1. **Limited Multi-tenancy**
   - ScalyClaw designed for small teams
   - AgentOS needs strict per-user data isolation

### From OpenClaw

#### ✅ Adopt
1. **Local-First Philosophy**
   - Self-contained, no cloud dependencies
   - Data stays on-premise

2. **File-Based Memory (AGENTS.md, SOUL.md)**
   - Human-readable personality files
   - Version controllable

3. **Session Model**
   - `main` session for direct chats
   - Group isolation
   - Session tools for agent-to-agent communication

4. **Gateway WebSocket Network**
   - Single control plane for all clients
   - Clean separation of concerns

5. **Canvas + A2UI**
   - Visual workspace for agent interaction
   - Structured JSONL envelopes for UI

6. **Extensive Channel Support**
   - 20+ channel implementations to reference
   - Well-tested patterns

#### ⚠️ Adapt
1. **Single-User → Multi-User**
   - OpenClaw designed for personal use
   - AgentOS adds Keycloak SSO + per-user isolation

2. **SQLite Scaling**
   - Works for single user, not for 100 concurrent
   - PostgreSQL required

3. **In-Process → Distributed**
   - OpenClaw runs as single process
   - AgentOS uses Celery for distributed tasks

#### ❌ Avoid
1. **Direct Provider SDK Calls**
   - OpenClaw calls providers directly
   - AgentOS uses LiteLLM Proxy for unified access

2. **Node-Only Ecosystem**
   - Limited ML tooling in Node.js
   - Python has better agent frameworks

### New Innovations for AgentOS

#### 🔥 Unique Features
1. **Three-Layer Security Gates**
   - Gate 1: JWT (Keycloak)
   - Gate 2: RBAC
   - Gate 3: Tool ACL
   - Covers every tool invocation

2. **Visual Canvas Workflows**
   - React Flow for node-based workflow design
   - Compile to LangGraph StateGraph
   - Schema-versioned for migration safety

3. **bge-m3 Embedding Model**
   - 1024-dimension vectors
   - Multilingual (Vietnamese support)
   - Self-hosted via FlagEmbedding

4. **Credential Containment**
   - AES-256 encrypted storage
   - Never visible to LLM, frontend, or logs
   - Auto-refresh for OAuth tokens

5. **Scheduler with User Context**
   - Celery jobs run as job owner, not service account
   - Prevents privilege escalation

6. **Structured Audit Logging**
   - JSONL format, Loki-compatible
   - Every tool call: who, what, when, allowed/denied

---

## Architecture Recommendations

### For AgentOS Design

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        RECOMMENDED AGENTOS ARCHITECTURE                 │
├─────────────────────────────────────────────────────────────────────────┤
│  FRONTEND (Next.js + CopilotKit)                                       │
│  ├── React Flow Canvas (workflow editor)                               │
│  ├── AG-UI Chat (streaming)                                            │
│  └── A2UI Renderer (generative widgets)                                │
├─────────────────────────────────────────────────────────────────────────┤
│  SECURITY RUNTIME (FastAPI)                                            │
│  ├── Gate 1: JWT Validation (Keycloak)                                 │
│  ├── Gate 2: RBAC Check                                                │
│  └── Gate 3: Tool ACL (middleware)                                     │
├─────────────────────────────────────────────────────────────────────────┤
│  AGENT ORCHESTRATION (LangGraph)                                       │
│  ├── Master Agent (Deep Agent pattern)                                 │
│  ├── Sub-agents (email, calendar, project, channel)                    │
│  └── Workflow StateGraph (compiled from canvas)                        │
├─────────────────────────────────────────────────────────────────────────┤
│  SERVICES                                                              │
│  ├── Tools (Python functions)                                          │
│  ├── Memory (3-tier: verbatim → episodes → facts)                      │
│  ├── MCP Clients (HTTP+SSE to MCP servers)                             │
│  └── Sandbox (Docker for unsafe code)                                  │
├─────────────────────────────────────────────────────────────────────────┤
│  INFRASTRUCTURE                                                        │
│  ├── PostgreSQL + pgvector (data + vectors)                            │
│  ├── Redis (Celery broker + cache)                                     │
│  ├── Keycloak (SSO + RBAC)                                             │
│  ├── LiteLLM Proxy (unified LLM access)                                │
│  └── Celery Workers (distributed execution)                            │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Security-First**
   - Three gates on every tool call
   - Credentials never exposed
   - Per-user memory isolation

2. **Scalability**
   - Horizontal scaling via Celery workers
   - PostgreSQL for concurrent access
   - Redis for queue and caching

3. **Developer Experience**
   - Hot-reload for development
   - Type-safe with Pydantic
   - Clear module boundaries

4. **Enterprise-Ready**
   - Keycloak SSO integration
   - Audit logging
   - On-premise deployment

---

## Implementation Priorities

### Phase 1: Foundation (Learn from OpenClaw)
- ✅ JWT + Keycloak integration
- ✅ Basic agent with tools
- ✅ SQLite → PostgreSQL migration
- ✅ Channel gateway pattern

### Phase 2: Memory & Tools (Adapt from ScalyClaw)
- ✅ 3-tier memory system
- ✅ bge-m3 embeddings
- ✅ Tool registry with ACL
- ✅ MCP integration

### Phase 3: Scale & Security (Go Beyond)
- ✅ Docker sandbox
- ✅ Celery workers
- ✅ Visual canvas workflows
- ✅ Audit logging

### Phase 4: Polish (Best of Both)
- 🔄 A2UI generative widgets
- 🔄 Advanced channel adapters
- 🔄 Budget control
- 🔄 4-layer guards

---

## Conclusion

**ScalyClaw** demonstrates that horizontal scaling and hot-reload are achievable in a TypeScript-based agent platform. Its 4-layer security model and budget control are excellent patterns to emulate.

**OpenClaw** proves that local-first, personal AI assistants can be elegant and powerful. Its session model, canvas UI, and extensive channel support provide a blueprint for user experience.

**AgentOS** combines the best of both:
- OpenClaw's local-first philosophy + ScalyClaw's scalability
- Python's ML ecosystem (LangGraph, PydanticAI)
- Enterprise security (Keycloak, 3-layer gates)
- Visual workflow creation (React Flow → StateGraph)

The result is an enterprise-grade Agentic OS that can scale to ~100 users while maintaining security, observability, and developer experience.

---

## Sources

- https://github.com/scalyclaw/scalyclaw
- https://github.com/openclaw/openclaw
- https://docs.openclaw.ai
- Blitz AgentOS Architecture Document (docs/architecture/architecture.md)
- Blitz AgentOS Memory Analysis (docs/research/19-memory-management-analysis.md)

---

*Document generated: March 2026*
