# Phase 2 Design — Agent Core and Conversational Chat

**Date:** 2026-02-25
**Status:** Approved
**Phase goal:** Users can have a natural language conversation with a streaming AI agent that remembers the conversation, routes through LiteLLM, and has isolated per-user memory.

---

## Architecture Overview

Four sequential sub-plans, each independently testable:

```
02-01: LiteLLM config + model aliases
         ↓
02-02: LangGraph ReAct master agent + AG-UI streaming
         ↓
02-03: Short-term memory (conversation turns per user/conversation)
         ↓
02-04: Credential store (AES-256 table + encrypt/decrypt + CRUD API stub)
```

All LLM calls flow: `agent → get_llm("blitz/master") → LiteLLM Proxy → provider`.
All three security gates (JWT → RBAC → Tool ACL) from Phase 1 remain in place.

---

## 02-01: LiteLLM Proxy Configuration

**Goal:** All model aliases are live and routable before any agent code is written.

### What gets built

- `infra/litellm/config.yaml` — defines 4 model aliases with primary + fallback routing:
  - `blitz/master`: Ollama/Qwen2.5:72b → fallback Claude Sonnet 4.6
  - `blitz/fast`: Ollama/Llama3.2:3b → fallback gpt-4o-mini
  - `blitz/coder`: OpenRouter/Kimi k1.5 → fallback Claude Sonnet 4.6
  - `blitz/summarizer`: Ollama/Llama3.2:3b → fallback gpt-4o-mini
- `core/config.py` — `get_llm(alias: str) → ChatOpenAI` returns instance pointed at LiteLLM proxy
- `docker-compose.yml` — LiteLLM service with `extra_hosts: host.docker.internal:host-gateway` (Linux requirement for Ollama)

### Tests
- Each alias resolves without error
- `get_llm()` returns correct endpoint
- LiteLLM `/health` passes

### Out of scope
No agent code, no tool calls — proxy layer only.

---

## 02-02: Master Agent (ReAct + AG-UI Streaming)

**Goal:** User sends a message in the browser and sees tokens stream back in real-time.

### Agent design: ReAct loop

Single LangGraph graph; promotes to supervisor in Phase 3 by adding sub-agent nodes and routing edges — no rewrite required.

### LangGraph graph structure

```
START
  ↓
load_memory          ← reads last 20 turns from DB for this user/conversation
  ↓
master_agent         ← ReAct node: calls blitz/master via get_llm()
  ↓ (loop until done)
tool_executor        ← runs tools from tool_registry.py if agent requests one
  ↓
save_memory          ← writes new turns to DB
  ↓
END
```

### AG-UI wiring

- `gateway/runtime.py` — wraps LangGraph graph in CopilotKit `LangGraphAgent`, streams tokens via AG-UI protocol
- `/api/agents/chat` FastAPI route — receives AG-UI messages, extracts `user_id` from JWT + `conversation_id` from request header (frontend-generated UUID), invokes runtime
- Security: JWT → RBAC → Tool ACL gates apply before graph runs

### Frontend (full chat UI)

- `CopilotChat` component wired end-to-end
- Conversation list sidebar
- New conversation button
- Thinking/loading indicator while agent processes
- Markdown rendering for assistant responses

---

## 02-03: Short-Term Memory and Conversation Persistence

**Goal:** Agent has conversation context on every turn; user can resume a previous conversation with full history.

### Conversation ID

Frontend generates a UUID when the user starts a new conversation and passes it in every AG-UI request header. Backend is stateless — no extra round-trip on first message.

### Data model (`memory_conversations` table)

| Column | Type | Notes |
|--------|------|-------|
| `conversation_id` | UUID | Frontend-generated |
| `user_id` | UUID | From JWT — never from request body |
| `role` | TEXT | `"user"` \| `"assistant"` \| `"tool"` |
| `content` | TEXT | |
| `created_at` | TIMESTAMP | |

### Memory flow

- `load_memory` node: `SELECT * FROM memory_conversations WHERE user_id=$1 AND conversation_id=$2 ORDER BY created_at DESC LIMIT 20` — injects as message history into graph state
- `save_memory` node: inserts user turn + assistant response after graph completes
- Isolation: `WHERE user_id=$1` from JWT — cross-user access is physically impossible at query level

### New API endpoint

`GET /api/conversations` — returns all conversation IDs + first message snippet for the current user (powers sidebar).

### Tests
- Turn storage round-trip
- Isolation: query with wrong `user_id` returns empty
- History injection order correct
- User A cannot access User B's conversations

---

## 02-04: Credential Store (Stub)

**Goal:** Encryption infrastructure exists and is tested; no real OAuth flows wired yet.

### What gets built

- `user_credentials` table migration (schema already defined)
- `security/credentials.py`:
  - `encrypt_token(token: str) → tuple[bytes, bytes]` — AES-256-GCM via `cryptography` library
  - `decrypt_token(ciphertext: bytes, iv: bytes) → str`
  - `store_credential(user_id, provider, token)` — all parameterized on `user_id` from JWT
  - `get_credential(user_id, provider) → str`
  - `delete_credential(user_id, provider)`
- API: `GET /api/credentials`, `DELETE /api/credentials/{provider}` — no `POST` (OAuth callbacks are Phase 3)

### Tests
- Encrypt → decrypt round-trip
- Ciphertext differs from plaintext
- `user_id` isolation enforced on all queries

### Out of scope
No Google OAuth callback, no Microsoft OAuth — just the vault layer Phase 3 will write tokens into.

---

## Success Criteria (from ROADMAP.md)

1. User can send a message in web chat and see tokens stream back in real-time via AG-UI protocol
2. Master agent receives user messages, creates a plan, and can delegate tasks (delegation targets available in Phase 3)
3. Agent conversation turns are stored per user and per conversation — user can resume a previous conversation with context preserved
4. All LLM calls route through LiteLLM Proxy using model aliases (`blitz/master`, `blitz/fast`) — no direct provider SDK calls
5. User A cannot see User B's conversation history or memory (isolation enforced at query level)

---

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| ReAct loop (not supervisor or plan-and-execute) | Sufficient for Phase 2 chat; promotes to supervisor in Phase 3 by adding nodes/edges, no rewrite |
| Frontend-generated conversation UUID | Stateless backend; no extra round-trip on first message |
| Full chat UI in Phase 2 | Sidebar + markdown + loading indicator — production-ready chat surface |
| Credential store stub only | No OAuth flows needed until Phase 3 sub-agents; build vault infrastructure now |
| LiteLLM configured before agent code | Agent depends on proxy being live; strict build order enforced |
