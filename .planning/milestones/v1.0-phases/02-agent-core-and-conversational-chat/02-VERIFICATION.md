---
phase: 02-agent-core-and-conversational-chat
verified: 2026-02-26T10:00:00Z
status: passed
score: 25/25 must-haves verified
---

# Phase 2: Agent Core and Conversational Chat — Verification Report

**Phase Goal:** Users can have a natural language conversation with a streaming AI agent that remembers the conversation, routes through LiteLLM, and has isolated per-user memory
**Verified:** 2026-02-26T10:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can send a message in web chat and see tokens stream back in real-time via AG-UI protocol | VERIFIED | `CopilotKit` wrapper with `runtimeUrl="/api/copilotkit"` and `agent="blitz_master"` in `chat-panel.tsx:358-362`; runtime.py returns `StreamingResponse` for `agent/run`; `CopilotChat` component renders streaming tokens; UAT test 1 passed |
| 2 | Master agent receives user messages, creates a plan, and routes to save_memory (delegation targets Phase 3) | VERIFIED | `master_agent.py` graph: `START → load_memory → master_agent → _route_after_master → save_memory → END`; `_route_after_master()` always returns `"save_memory"` (stub by design per ROADMAP); graph compiled with `MemorySaver`; UAT test 1 passed |
| 3 | Agent conversation turns are stored per user and per conversation; user can resume with context preserved | VERIFIED | `_save_memory_node` saves new turns to `memory_conversations` table using DB turn count as dedup guard; `agent/connect` method in `runtime.py` replays DB turns as `TextMessageStart/Content/End` events on reconnect; `ConversationTurn` ORM with `user_id` + `conversation_id` composite index; UAT tests 2, 3 passed |
| 4 | All LLM calls route through LiteLLM Proxy using model aliases — no direct provider SDK calls | VERIFIED | `_master_node` calls `get_llm("blitz/master")` at line 120; `get_llm()` in `core/config.py:81-93` maps alias to `ChatOpenAI(base_url=f"{settings.litellm_url}/v1")`; zero direct `anthropic` or `openai` SDK imports in agent or gateway code |
| 5 | User A cannot see User B's conversation history or memory (isolation enforced at query level) | VERIFIED | `load_recent_turns()` filters `.where(ConversationTurn.user_id == user_id, ConversationTurn.conversation_id == conversation_id)`; `list_conversations()` filters `.where(ConversationTurn.user_id == user["user_id"])`; user_id always from `Depends(get_current_user)` never from request body; `_save_memory_node` uses contextvar fallback tied to JWT-validated user |

**Score:** 5/5 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/agents/state/types.py` | BlitzState TypedDict with messages, user_id, conversation_id, initial_message_count | VERIFIED | 31 lines; `BlitzState` TypedDict with `messages: Annotated[list[BaseMessage], add_messages]`, `user_id: UUID | None`, `conversation_id: UUID | None`, `initial_message_count: int`; evolution comment documents Phase 2 state and future expansion plan |
| `backend/agents/master_agent.py` | LangGraph graph with load_memory/master_agent/save_memory nodes + contextvar fallbacks | VERIFIED | 264 lines; full graph topology `START → load_memory → master_agent → [_route_after_master] → save_memory → END`; both `_load_memory_node` and `_save_memory_node` have contextvar fallback (`current_user_ctx.get()` / `current_conversation_id_ctx.get()`); DB turn-count dedup guard; MemorySaver checkpointer |
| `backend/gateway/runtime.py` | CopilotKit endpoint: `info`, `agent/run`, `agent/connect` methods with 3-gate security | VERIFIED | 281 lines; handles all 3 methods; Gate 1 `Depends(get_current_user)`, Gate 2 `has_permission()`, Gate 3 `check_tool_acl()`; `agent/connect` replays turns as `TextMessageStart/Content/End` events; contextvar injection in `event_generator()` |
| `backend/memory/short_term.py` | `load_recent_turns()` and `save_turn()` with user_id isolation | VERIFIED | 85 lines; `load_recent_turns()` double-parameterized on `user_id` AND `conversation_id`; `save_turn()` creates `ConversationTurn` row without commit (caller owns transaction); both functions documented with isolation invariant |
| `backend/security/credentials.py` | AES-256-GCM `encrypt_token()` / `decrypt_token()` + `store_credential()` / `get_credential()` / `delete_credential()` | VERIFIED | 203 lines; `AESGCM(key)` with random 12-byte nonce per encryption; `store_credential()` uses select-then-upsert pattern; zero token values in any log calls; isolation enforced in all queries |
| `backend/core/models/credentials.py` | `UserCredential` ORM model with ciphertext + iv columns | VERIFIED | 46 lines; `__tablename__ = "user_credentials"`; `ciphertext: LargeBinary`, `iv: LargeBinary`; `UniqueConstraint("user_id", "provider")`; `user_id` indexed |
| `backend/core/models/memory.py` | `ConversationTurn` ORM model with user_id + conversation_id | VERIFIED | 36 lines; `__tablename__ = "memory_conversations"`; `user_id: UUID`, `conversation_id: UUID`, `role: str`, `content: str`, `created_at`; both `user_id` and `conversation_id` indexed |
| `backend/api/routes/conversations.py` | `GET /api/conversations/` list endpoint with user isolation | VERIFIED | 252 lines; `list_conversations()` with correlated subquery for first user message as auto-title; custom title override from `conversation_titles` table; PATCH `/{id}/title`, DELETE `/{id}`, GET `/{id}/messages` also implemented; all parameterized on `user["user_id"]` from JWT |
| `backend/api/routes/credentials.py` | `GET /api/credentials` + `DELETE /api/credentials/{provider}` | VERIFIED | 90 lines; `list_connected_providers()` returns `ConnectedProvider(provider, connected_at)` — never ciphertext or tokens; `disconnect_provider()` calls `delete_credential()` with `user["user_id"]` from JWT; 404 on missing provider |
| `backend/api/routes/user_instructions.py` | `GET /api/user/instructions` + `PUT /api/user/instructions` + `get_user_instructions()` helper | VERIFIED | 117 lines; `get_user_instructions()` exported and called from `_master_node`; upsert pattern; `max_length=4000`; logs truncated length not content |
| `backend/core/context.py` | `current_user_ctx` + `current_conversation_id_ctx` contextvars | VERIFIED | 40 lines; `ContextVar[UserContext]` and `ContextVar[UUID]`; set by runtime.py before graph invocation; reset in finally block; read by graph nodes as fallback when BlitzState fields are None |
| `backend/core/config.py` | `get_llm()` with 4-alias mapping to LiteLLM proxy | VERIFIED | 93 lines; `model_map` for `blitz/master`, `blitz/fast`, `blitz/coder`, `blitz/summarizer`; all return `ChatOpenAI(base_url=f"{settings.litellm_url}/v1")`; `streaming=True`; `credential_encryption_key` field added for Phase 2 vault |
| `frontend/src/app/api/copilotkit/route.ts` | Next.js proxy with server-side JWT injection | VERIFIED | 73 lines; reads `accessToken` from `auth()` server-side session; injects `Authorization: Bearer` header; forwards `CopilotKit` protocol headers; streams response body; never exposes token to browser |
| `frontend/src/components/chat/chat-panel.tsx` | CopilotKit streaming with slash commands, edit message, export | VERIFIED | 372 lines; `CopilotKit` with `runtimeUrl`, `agent`, `threadId`; `SlashCommandInput` handles `/new` and `/clear`; `EditableUserMessage` shows edit icon on hover; `exportAsMarkdown()` downloads `.md` file; `onInProgress` callback triggers sidebar refresh |
| `frontend/src/components/chat/chat-layout.tsx` | ChatLayout with sidebar + panel + conversation management | VERIFIED | 101 lines; `ConversationSidebar` + `ChatPanel` wired; `refreshConversations()` calls `/api/conversations` proxy; `handleNewConversation()` generates UUID via `crypto.randomUUID()`; `onConversationUpdate={refreshConversations}` passed to `ChatPanel` |
| `frontend/src/app/chat/page.tsx` | Server Component that SSR-fetches conversations and renders ChatLayout | VERIFIED | 37 lines; `auth()` server-side; `fetchConversations()` with `Bearer ${accessToken}`; redirects to `/login` if no session; passes `initialConversations` and `userEmail` to `ChatLayout` |
| `frontend/src/app/settings/page.tsx` | Settings page with custom instructions textarea + save | VERIFIED | 81 lines; `useEffect` fetches from `/api/user/instructions/`; `handleSave()` does `PUT` to `/api/user/instructions/`; 4000 char limit with counter; saved confirmation |
| `frontend/src/app/api/user/instructions/route.ts` | Next.js proxy for user instructions API | VERIFIED | 62 lines; `GET` and `PUT` handlers; `auth()` server-side; `Bearer` token injected; response forwarded transparently |
| `frontend/src/app/api/conversations/route.ts` | Next.js proxy for conversations list (sidebar refresh) | VERIFIED | 31 lines; `GET` handler; `auth()` server-side; `Bearer` token injected; called by `ChatLayout.refreshConversations()` after AI finishes responding |
| `backend/alembic/versions/002_memory_conversations.py` | DB migration for `memory_conversations` table | VERIFIED | Creates `memory_conversations` with `id, conversation_id, user_id, role, content, created_at`; composite index `ix_memory_conversations_user_conversation` on `(user_id, conversation_id, created_at)` for load query performance |
| `backend/alembic/versions/003_user_credentials.py` | DB migration for `user_credentials` table | VERIFIED | Creates `user_credentials` with `ciphertext: LargeBinary`, `iv: LargeBinary`; `UniqueConstraint("user_id", "provider")`; branches from `001` in parallel with `002` |
| `backend/alembic/versions/9754fd080ee2_merge_002_memory_and_003_credentials.py` | Merge migration resolving parallel 002+003 heads | VERIFIED | `down_revision = ("002", "003")`; merges two parallel branches so `alembic upgrade head` works with a single head |
| `backend/alembic/versions/004_user_instructions.py` | DB migration for `user_instructions` table | VERIFIED | Creates `user_instructions` with `user_id: unique index`, `instructions: Text`, `created_at`, `updated_at`; one row per user (upsert pattern) |
| `backend/alembic/versions/005_conversation_titles.py` | DB migration for `conversation_titles` table | VERIFIED | Creates `conversation_titles` with composite PK `(user_id, conversation_id)`; supports custom rename via `PATCH /api/conversations/{id}/title` |
| `backend/tests/test_runtime.py` | CopilotKit endpoint security gate tests | VERIFIED | 3 tests: route not 404, 401 without JWT, 403 for role with no `chat` permission; dependency override pattern |
| `backend/tests/test_conversations.py` | Conversations API security gate tests | VERIFIED | 2 tests: 401 without JWT, route exists |
| `backend/tests/test_credentials_api.py` | Credentials API security gate tests | VERIFIED | 4 tests: GET 401, GET exists, DELETE 401, DELETE exists |
| `backend/tests/test_user_instructions.py` | User instructions API security gate tests | VERIFIED | 4 tests: GET 401, PUT 401, GET exists, PUT exists |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `frontend/chat-panel.tsx CopilotKit` | `frontend/api/copilotkit/route.ts` | `runtimeUrl="/api/copilotkit"` | WIRED | `chat-panel.tsx:360`: `runtimeUrl="/api/copilotkit"`; proxy at `frontend/src/app/api/copilotkit/route.ts` forwards to backend |
| `frontend/api/copilotkit/route.ts` | `backend/gateway/runtime.py POST /api/copilotkit` | `fetch(BACKEND_URL + "/api/copilotkit", {Authorization: Bearer})` | WIRED | `route.ts:37`: `fetch(\`\${BACKEND_URL}/api/copilotkit\`, {method:"POST", headers:{Authorization:...}})`; Bearer token from server-side `auth()` |
| `backend/gateway/runtime.py` | `backend/agents/master_agent.py create_master_graph()` | `_master_graph = create_master_graph()` at module load | WIRED | `runtime.py:66`: `_master_graph = create_master_graph()`; `_agent = LangGraphAGUIAgent(graph=_master_graph)` |
| `backend/gateway/runtime.py` | `core/context.py` contextvars | `current_user_ctx.set(user)` + `current_conversation_id_ctx.set(conversation_id)` | WIRED | `runtime.py:262-263`: both set inside `event_generator()` before `_agent.run(input_data)` streams; reset in `finally` block |
| `backend/agents/master_agent.py _master_node` | `core/config.py get_llm()` | `llm = get_llm("blitz/master")` | WIRED | `master_agent.py:120`: `llm = get_llm("blitz/master")`; never direct provider SDK |
| `backend/core/config.py get_llm()` | `http://litellm:4000/v1` | `base_url=f"{settings.litellm_url}/v1"` | WIRED | `config.py:90`: `base_url=f"{settings.litellm_url}/v1"`; `litellm_url` loaded from `.env` |
| `backend/agents/master_agent.py _master_node` | `api/routes/user_instructions.py get_user_instructions()` | `await get_user_instructions(user["user_id"], session)` | WIRED | `master_agent.py:127`: custom instructions appended to system prompt if non-empty; fetched via `current_user_ctx.get()` |
| `backend/agents/master_agent.py _load_memory_node` | `memory/short_term.py load_recent_turns()` | `await load_recent_turns(session, user_id=user_id, conversation_id=conversation_id, n=20)` | WIRED | `master_agent.py:74`: call with user_id from BlitzState or contextvar fallback |
| `backend/agents/master_agent.py _save_memory_node` | `memory/short_term.py save_turn()` | loop calling `await save_turn(session, ...)` | WIRED | `master_agent.py:206-219`: saves HumanMessage and AIMessage turns; DB count used as dedup guard; single `await session.commit()` after loop |
| `backend/memory/short_term.py load_recent_turns` | `core/models/memory.py ConversationTurn` | `select(ConversationTurn).where(user_id==, conversation_id==)` | WIRED | `short_term.py:40-46`: double-parameterized SQLAlchemy select; returns `list[ConversationTurn]` |
| `backend/security/credentials.py` | `core/models/credentials.py UserCredential` | `select(UserCredential).where(user_id==, provider==)` | WIRED | `credentials.py:118-123`: parameterized select; `store_credential()` / `get_credential()` / `delete_credential()` all use this pattern |
| `backend/api/routes/conversations.py` | `security/deps.py get_current_user()` | `Depends(get_current_user)` | WIRED | `conversations.py:37`: `user: UserContext = Depends(get_current_user)` |
| `backend/api/routes/credentials.py` | `security/credentials.py delete_credential()` | `await delete_credential(session, user_id=user["user_id"], provider=provider)` | WIRED | `credentials.py:80`: `delete_credential()` enforces `WHERE user_id=$1` in its own query |
| `backend/main.py` | all Phase 2 routers | `app.include_router(...)` | WIRED | `main.py:10-52`: `credentials.router`, `conversations.router`, `user_instructions.router`, `runtime.router` all included; runtime.router has no prefix (registered at `/api/copilotkit`) |
| `frontend/chat-layout.tsx refreshConversations` | `frontend/api/conversations/route.ts` | `fetch("/api/conversations", {cache:"no-store"})` | WIRED | `chat-layout.tsx:40-43`: `fetch("/api/conversations")` called after `onConversationUpdate`; proxy injects Bearer server-side |
| `frontend/settings/page.tsx` | `frontend/api/user/instructions/route.ts` | `fetch("/api/user/instructions/", ...)` | WIRED | `settings/page.tsx:18,28`: GET on mount + PUT on save; proxy at `/api/user/instructions/route.ts` injects Bearer |
| `frontend/chat-panel.tsx onInProgress` | `chat-layout.tsx refreshConversations` | `onConversationUpdate` prop callback | WIRED | `chat-panel.tsx:219`: `onConversationUpdate?.()` called on `inProgress` true→false transition; `chat-layout.tsx:96`: `onConversationUpdate={refreshConversations}` |

---

## Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| AGNT-01 | User can send natural language messages and receive streaming responses via AG-UI chat | SATISFIED | `CopilotKit` → `/api/copilotkit` proxy → `runtime.py agent/run` → `LangGraphAGUIAgent._agent.run()` → `StreamingResponse`; `CopilotChat` renders streamed tokens; UAT test 1 passed end-to-end in browser |
| AGNT-02 | Master agent plans multi-step tasks and delegates to sub-agents (delegation targets Phase 3) | SATISFIED (by design) | `_route_after_master()` stub always returns `"save_memory"` — explicitly documented as Phase 2 design in `master_agent.py:229-233` and ROADMAP.md; Phase 3 adds sub-agent edges without restructuring this graph. This is NOT a gap. |
| AGNT-07 | All LLM calls route through LiteLLM Proxy using model aliases | SATISFIED | `_master_node` exclusively uses `get_llm("blitz/master")` — the only LLM call in the graph; `get_llm()` enforces routing to `{litellm_url}/v1`; zero direct provider SDK imports in agents/ or gateway/; `test_config.py::test_get_llm_maps_all_aliases` verifies all 4 alias mappings |
| MEMO-01 | System stores conversation turns per user and conversation (short-term memory) | SATISFIED | `ConversationTurn` ORM persisted in `memory_conversations` table; `_save_memory_node` saves each new HumanMessage and AIMessage turn with `user_id` + `conversation_id`; migration `002` created the table with composite index; UAT test 3 (conversation persists after page refresh) confirmed |
| MEMO-05 | All memory queries parameterized on user_id from JWT — no cross-user reads | SATISFIED | `load_recent_turns()`: `WHERE user_id=$1 AND conversation_id=$2`; `save_turn()`: user_id from contextvar (set by runtime.py from validated JWT, never from request body); `list_conversations()`: `WHERE user_id=$1`; `get_credential()` / `delete_credential()`: `WHERE user_id=$1 AND provider=$2`; security invariant documented in module-level docstrings of `short_term.py` and `credentials.py` |
| INTG-04 | User OAuth tokens stored AES-256 encrypted in PostgreSQL, resolved internally by user_id | SATISFIED | `encrypt_token()` uses `AESGCM` with random 12-byte nonce per call; `ciphertext + iv` stored in `user_credentials` table; `get_credential()` decrypts internally; `ConnectedProvider` response omits all token/ciphertext fields; `credential_encryption_key` from settings (hex-encoded 32-byte key); key management documented as MVP-scope (post-MVP KMS noted in CLAUDE.md) |

---

## Anti-Patterns Found

No blocking anti-patterns. Findings categorized:

| File | Pattern | Severity | Assessment |
|------|---------|----------|------------|
| `backend/agents/master_agent.py:96` | `"capabilities are coming soon"` | Info | User-facing honesty message in `_DEFAULT_SYSTEM_PROMPT` — this is intentional documentation for the LLM to explain Phase 2 limitations to the user. Not a code stub. |
| `frontend/src/components/chat/chat-panel.tsx:59` | `"coming soon"` in `SYSTEM_PROMPT` constant | Info | Same rationale — honest capability disclosure in system prompt. Not a stub. |
| `frontend/src/components/chat/chat-panel.tsx:126,324` | `placeholder=` in textarea/input | Info | HTML form placeholder attributes — UI design, not stub patterns. |
| `frontend/src/app/settings/page.tsx:64` | `placeholder=` in textarea | Info | HTML form placeholder attribute. |

No TODO/FIXME/XXX comments found in any Phase 2 implementation files.
No empty handlers (`return {}`, `return null`) found in critical paths.
No credential values in any log calls (verified in `credentials.py`, `runtime.py`, `conversations.py`).
`_route_after_master()` always returning `"save_memory"` is an intentional documented Phase 2 design — explicitly noted in both the source code docstring and ROADMAP Phase 2 plans.

---

## Human Verification Required

### 1. Streaming Chat — Token-by-Token Display

**Test:** Navigate to `http://localhost:3000/chat`. Type a message (e.g. "Explain quantum entanglement in 3 sentences") and press Enter.
**Expected:** Text streams in progressively — visible token-by-token rendering, not a single response pop-in. A "Stop" button appears during generation.
**Why human:** Real-time streaming rendering requires visual confirmation; cannot verify token timing programmatically.
**Evidence:** UAT test 1 passed (2026-02-26) with fix note: "MemorySaver on graph.compile" resolved streaming.

### 2. Conversation Persistence Across Page Refresh

**Test:** Send a message and receive a response. Note the first few words of the AI response. Refresh the page (F5). Click the same conversation in the sidebar.
**Expected:** The full conversation restores — user message and AI response both visible in the chat panel. The sidebar still shows the conversation title.
**Why human:** Requires real DB persistence verification across a page reload event.
**Evidence:** UAT test 3 passed (2026-02-26) with fix note: "agent/connect replaced StateSnapshotEvent with TextMessage events per turn."

### 3. Custom Instructions Respected by Agent

**Test:** Navigate to `http://localhost:3000/settings`. Enter "Always respond in Vietnamese." Click Save. Return to chat, start a new conversation (/new), send "Hello, who are you?"
**Expected:** The AI responds entirely in Vietnamese, reflecting the custom instructions injected into the system prompt.
**Why human:** Requires actual LLM call through the full stack; system prompt injection cannot be verified by static analysis alone.
**Evidence:** UAT test 8 passed (2026-02-26).

### 4. Memory Isolation — Multi-User Verification

**Test:** Log in as User A, start a conversation and send messages. Log out, log in as User B (different Keycloak account). Check the conversation sidebar and attempt to access User A's conversation_id via `GET /api/conversations/`.
**Expected:** User B sees only their own conversations (empty if no prior conversations). User A's conversations and messages are invisible.
**Why human:** Cross-user isolation requires two active browser sessions with different Keycloak identities.
**Evidence:** Enforced at code level (`WHERE user_id=$1` on all queries from JWT-validated user_id); cannot verify without two test accounts.

### 5. Credential API Security — Token Never in Response

**Test:** Run `curl -H "Authorization: Bearer <token>" http://localhost:8000/api/credentials/`
**Expected:** Response is a JSON array. If credentials exist, each entry has only `provider` and `connected_at` fields — no `ciphertext`, `iv`, `token`, or `access_token` fields.
**Why human:** Verifying response shape against running backend with actual stored credentials.
**Evidence:** UAT test 9 passed (2026-02-26); `ConnectedProvider` Pydantic model verified to exclude sensitive fields.

---

## Gaps Summary

No gaps. All 25 must-haves from Plans 02-01 through 02-05 are verified. The phase goal is achieved:

- **AG-UI Streaming Chat:** `CopilotKit` + `LangGraphAGUIAgent` + `StreamingResponse` deliver real-time token streaming through the 3-gate security chain. The `agent/connect` method restores conversation history on page reload or conversation switch.

- **LiteLLM Routing:** `get_llm("blitz/master")` is the sole LLM entry point, routing through `http://litellm:4000/v1`. Zero direct provider SDK calls exist in agent or gateway code. All 4 model aliases (`blitz/master`, `blitz/fast`, `blitz/coder`, `blitz/summarizer`) are wired.

- **Short-Term Memory:** `ConversationTurn` rows stored in `memory_conversations` per user and per conversation. `_save_memory_node` uses DB turn count as a dedup guard (not `initial_message_count`, which LangGraphAGUIAgent does not populate). `_load_memory_node` skips loading when CopilotKit already provides message history in state.

- **Memory Isolation:** Every memory read/write query is parameterized on `user_id` extracted from JWT by `get_current_user()`. The `user_id` is propagated to graph nodes via Python contextvars (never via request body or agent state).

- **Credential Vault:** AES-256-GCM encrypt/decrypt implemented with NIST-compliant 12-byte random nonce per encryption. `ciphertext + iv` stored in `user_credentials`. Decrypted tokens are returned from `get_credential()` only to internal backend callers — never logged, never returned to frontend.

- **API Surface:** 5 routers registered: `health`, `agents`, `credentials`, `conversations`, `user_instructions` + `runtime` (CopilotKit). All protected by `Depends(get_current_user)` where appropriate. 13 new tests added; existing 58 tests from Phase 1 unaffected.

- **Frontend:** Full chat UI with sidebar, streaming, slash commands (`/new`, `/clear`), edit message, export markdown, settings page with custom instructions. All backend calls proxy through Next.js API routes with server-side JWT injection — token never touches the browser.

- **Alembic Migrations:** 4 new migrations (002-005) + 1 merge migration resolve the parallel 002/003 branch. Migration chain: `001 → {002 || 003} → 9754fd080ee2 (merge) → 004 → 005`.

Note on AGNT-02: The `_route_after_master()` conditional stub that always routes to `save_memory` is intentional Phase 2 architecture. Phase 3 adds sub-agent node edges without restructuring the graph topology. This is documented in both the source code and ROADMAP.md and is not a gap.

---

_Verified: 2026-02-26T10:00:00Z_
_Verifier: Claude (gsd-verifier)_
