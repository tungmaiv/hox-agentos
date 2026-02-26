---
phase: 02-agent-core-and-conversational-chat
plan: "05"
subsystem: ui
tags: [copilotkit, langgraph, streaming, chat-ui, nextjs, slash-commands, custom-instructions, markdown, memory, tailwind]

# Dependency graph
requires:
  - phase: 02-02
    provides: "blitz_master LangGraphAgent, POST /api/copilotkit with 3-gate security, current_user_ctx"
  - phase: 02-03
    provides: "memory_conversations table, load/save memory nodes, threadId extraction, GET /api/conversations/"
  - phase: 02-04
    provides: "user_credentials table, AES-256-GCM vault, credential isolation pattern"
  - phase: 01-01
    provides: "next-auth v5 with Keycloak, server-side session with accessToken, auth() server function"

provides:
  - Next.js /api/copilotkit proxy route forwarding AG-UI requests to FastAPI with server-side JWT injection
  - ChatLayout: responsive sidebar+panel layout with mobile hamburger collapse
  - ConversationSidebar: conversation list, New Conversation button, rename/delete context menu, relative timestamps, Settings link
  - ChatPanel: CopilotKit streaming with agent='blitz_master', runtimeUrl='/api/copilotkit', threadId=conversationId
  - Slash commands /new and /clear intercepted in custom Input component before send
  - Export conversation as markdown browser download via createObjectURL
  - Edit message: EditableUserMessage component with pencil icon re-populates input for resend
  - user_instructions PostgreSQL table (Alembic migration 004)
  - GET /api/user/instructions + PUT /api/user/instructions (upsert, JWT-isolated)
  - master_agent._master_node: loads custom instructions from DB, prepends as SystemMessage
  - /settings page with textarea + save button for custom instructions
  - 94 backend tests pass; 0 TypeScript errors

affects:
  - 03+ (custom instructions pattern reusable for sub-agent system prompts)
  - 03+ (ChatPanel threadId and agent name are fixed — any agent name change breaks frontend)
  - 04+ (Canvas — runtimeUrl='/api/copilotkit' is the shared endpoint for all CopilotKit interactions)

# Tech tracking
tech-stack:
  added:
    - "@copilotkit/react-core@1.51.4"
    - "@copilotkit/react-ui@1.51.4"
    - "react-markdown@10.1.0"
    - "react-syntax-highlighter@16.1.0"
    - "date-fns@4.1.0"
    - "@types/react-syntax-highlighter@15.5.13 (dev)"
  patterns:
    - "CopilotKit v1.51.4: CopilotKit component has threadId and agent props (confirmed in types)"
    - "useCopilotChatInternal (not useCopilotChat) exposes messages and reset — public hook omits these"
    - "Custom Input prop on CopilotChat receives onSend: (text: string) => Promise<Message> — use for slash command interception"
    - "Custom UserMessage prop on CopilotChat receives UserMessageProps with message.content — use for edit icon"
    - "Next.js proxy route: session as unknown as Record<string, unknown> for double-cast to access accessToken"

key-files:
  created:
    - frontend/src/app/api/copilotkit/route.ts
    - frontend/src/components/chat/chat-layout.tsx
    - frontend/src/components/chat/conversation-sidebar.tsx
    - frontend/src/components/chat/chat-panel.tsx
    - backend/core/models/user_instructions.py
    - backend/alembic/versions/004_user_instructions.py
    - backend/api/routes/user_instructions.py
    - backend/tests/test_user_instructions.py
    - frontend/src/app/settings/page.tsx
  modified:
    - frontend/package.json (added CopilotKit + markdown + date-fns packages)
    - frontend/pnpm-lock.yaml
    - frontend/src/app/chat/page.tsx (replaced placeholder with ChatLayout + server-side conversation fetch)
    - backend/agents/master_agent.py (added custom instructions injection in _master_node)
    - backend/main.py (registered user_instructions.router)

key-decisions:
  - "useCopilotChatInternal over useCopilotChat for messages + reset: public useCopilotChat omits messages and setMessages in its return type (Omit<UseCopilotChatReturn, 'messages'...>); the internal hook has both"
  - "Custom Input component for slash command interception: CopilotChat.onSubmitMessage is void|Promise<void> — cannot return false to cancel. Custom Input receives onSend prop and decides whether to call it"
  - "Custom UserMessage component for edit icon: CopilotChat accepts UserMessage prop (React.ComponentType<UserMessageProps>); message.content is string | unknown for content from AG-UI"
  - "ChatMessage local type for export: @copilotkit/shared is not a direct dependency of the project — imported via pnpm's hoisted path. Defined a minimal local ChatMessage interface to avoid unresolvable module error"
  - "session as unknown as Record<string, unknown> double cast: TypeScript strict mode requires intermediate unknown cast to satisfy TS2352 for Session type extension (established pattern from 01-04/auth.ts)"
  - "Migration 004 down_revision = '9754fd080ee2': the merge migration from 02-03 is the current single head; 004 branches from it"
  - "Migration applied via docker exec psql: .env absent from host; alembic CLI requires DATABASE_URL from settings"

patterns-established:
  - "CopilotKit proxy pattern: Next.js /api/copilotkit route injects server-side JWT, streams backend SSE response to browser"
  - "Slash command pattern: custom Input component wraps onSend, intercepts /new and /clear before calling onSend"
  - "Edit message pattern: custom UserMessage component + pendingInputRef shared with custom Input for pre-fill on edit click"
  - "Custom instructions injection: get_user_instructions(user_id, session) called in _master_node via current_user_ctx contextvar; result prepended as SystemMessage; LookupError falls back gracefully for tests"

requirements-completed:
  - AGNT-01

# Metrics
duration: ~25min (Tasks 1+2 automated; human verify checkpoint approved)
completed: "2026-02-25"
---

# Phase 2 Plan 05: Chat UI and Custom Instructions Summary

**CopilotKit v1.51.4 streaming chat with sidebar, slash commands (/new, /clear), markdown export, edit message, and per-user custom instructions injected into master agent system prompt — Phase 2 complete, 94 backend tests pass**

## Performance

- **Duration:** ~25 min (2 automated tasks + human checkpoint verification)
- **Started:** 2026-02-25T04:45:40Z
- **Completed:** 2026-02-25T09:04:01Z (checkpoint approved)
- **Tasks:** 2 automated + 1 human-verify checkpoint
- **Files modified:** 14 (9 created, 5 modified)

## Accomplishments

- Installed CopilotKit v1.51.4 frontend packages (`@copilotkit/react-core`, `@copilotkit/react-ui`), `react-markdown`, `date-fns` — TypeScript strict 0 errors
- Next.js `/api/copilotkit` proxy route: reads `accessToken` from server-side next-auth session, injects as `Authorization: Bearer`, streams backend SSE response to browser — browser never sees token
- Full chat layout: `ChatLayout` (sidebar + panel), `ConversationSidebar` (list, New Conversation, rename/delete context menu, relative timestamps, Settings link), `ChatPanel` (CopilotKit streaming with `agent='blitz_master'`, `runtimeUrl='/api/copilotkit'`, `threadId=conversationId`)
- Slash commands via custom `Input` component: `/new` calls `onNewConversation`, `/clear` calls `reset()` — intercepted before `onSend` is called so nothing reaches the agent
- Export as markdown: `useCopilotChatInternal().messages` serialized to `.md` via `URL.createObjectURL`, browser download triggered
- Edit message: custom `UserMessage` component shows pencil icon on hover, click fills shared `pendingInputRef` which `SlashCommandInput` reads on next render
- `user_instructions` table (Alembic 004, `down_revision='9754fd080ee2'`): user_id unique, instructions text, timestamps
- `GET /api/user/instructions/` + `PUT /api/user/instructions/` with JWT guard and upsert (select-then-insert/update)
- `master_agent._master_node` extended: calls `get_user_instructions(user_id, session)` via `current_user_ctx`, prepends non-empty result as `SystemMessage` — graceful `LookupError` fallback for tests
- `/settings` page: textarea with 4000-char limit, character counter, save button, "Back to chat" link
- 94 backend tests pass (was 90), 0 TypeScript errors, human-verify checkpoint approved

## Task Commits

1. **Task 1: Next.js proxy route + full chat UI (CopilotKit streaming)** - `e6f13d7` (feat)
2. **Task 2: Custom instructions — DB table + GET/PUT API + agent injection** - `da14115` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `frontend/src/app/api/copilotkit/route.ts` - Next.js proxy forwarding AG-UI with server-side JWT
- `frontend/src/components/chat/chat-layout.tsx` - Sidebar+panel layout, mobile collapse, conversation state
- `frontend/src/components/chat/conversation-sidebar.tsx` - Conversation list, rename/delete, Settings link
- `frontend/src/components/chat/chat-panel.tsx` - CopilotKit streaming, slash commands, export, edit message
- `frontend/src/app/chat/page.tsx` - Server component: fetches conversations, renders ChatLayout
- `frontend/src/app/settings/page.tsx` - Custom instructions textarea + save via PUT /api/user/instructions/
- `backend/core/models/user_instructions.py` - UserInstructions ORM model
- `backend/alembic/versions/004_user_instructions.py` - Migration 004 (down_revision=9754fd080ee2)
- `backend/api/routes/user_instructions.py` - GET/PUT endpoints + get_user_instructions() helper
- `backend/agents/master_agent.py` - _master_node extended with custom instructions injection
- `backend/main.py` - Registered user_instructions.router under /api
- `backend/tests/test_user_instructions.py` - 4 security gate tests
- `frontend/package.json` - Added CopilotKit, react-markdown, date-fns packages
- `frontend/pnpm-lock.yaml` - Updated lockfile

## CopilotKit v1.51.4 Prop Inventory

| Component/Hook | Prop/Return | Type | Notes |
|---|---|---|---|
| `CopilotKit` | `runtimeUrl` | `string` | Next.js proxy URL |
| `CopilotKit` | `agent` | `string` | Must match backend LangGraphAgent name |
| `CopilotKit` | `threadId` | `string` | Sent as `threadId` in AG-UI request body |
| `CopilotChat` | `instructions` | `string` | System prompt |
| `CopilotChat` | `labels` | `CopilotChatLabels` | title, initial welcome, placeholder |
| `CopilotChat` | `Input` | `React.ComponentType<InputProps>` | Custom input; `onSend` is the send callback |
| `CopilotChat` | `UserMessage` | `React.ComponentType<UserMessageProps>` | Custom user bubble |
| `CopilotChat` | `onSubmitMessage` | `(msg: string) => void\|Promise<void>` | Called after send — CANNOT cancel |
| `useCopilotChat` (public) | `reset` | `() => void` | Clears messages; `messages` is NOT in public return |
| `useCopilotChatInternal` | `messages` | `Message[]` | AG-UI format; `role: "user"\|"assistant"\|...` |
| `useCopilotChatInternal` | `reset` | `() => void` | Clears messages |
| `InputProps` | `onSend` | `(text: string) => Promise<Message>` | Call to send; skip call to intercept |
| `UserMessageProps` | `message` | `UserMessage\|undefined` | `message.content` is `string\|unknown` |

## Decisions Made

- **`useCopilotChatInternal` for `messages` + `reset`:** The public `useCopilotChat` Omit-s `messages`, `sendMessage`, `setMessages`, and `deleteMessage` from its return type. Only the internal hook exposes `messages` for the export function. Both `reset()` functions are equivalent.
- **Custom `Input` component for slash command interception:** `CopilotChat.onSubmitMessage` callback signature is `void | Promise<void>` — there is no way to return `false` or cancel the send from it. The correct interception point is a custom `Input` component that receives `onSend: (text: string) => Promise<Message>` and decides whether to call it. Slash commands skip `onSend` entirely.
- **`pendingInputRef` + `setPendingInput` for edit re-populate:** `CopilotChat` does not expose a `setInput` method. The custom `Input` component owns its own `inputValue` state. To pre-fill from outside (edit click), a `MutableRefObject<string>` is passed from `ChatPanelInner` down to both `SlashCommandInput` (reads on mount/effect) and `EditableUserMessage` (writes on click).
- **Local `ChatMessage` interface for export:** `@copilotkit/shared` is not a direct project dependency (it lives in pnpm's virtual store under `.pnpm/`). Importing it directly caused TS2307. Defined a minimal local `interface ChatMessage { role: string; content?: string | unknown }` instead — sufficient for the export serialization.
- **Migration 004 applied via docker exec psql:** Consistent with migrations 001–003; the host has no `.env` so alembic CLI fails. Created the table via direct SQL with trust auth inside the container, then updated `alembic_version` via INSERT ON CONFLICT DO NOTHING.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `useCopilotChat` public hook does not expose `messages` — switched to `useCopilotChatInternal`**

- **Found during:** Task 1 (implementing export function)
- **Issue:** Plan specified `const { messages, clearMessages } = useCopilotChat()`. The public `useCopilotChat` return type uses `Omit<UseCopilotChatReturn, "messages" | "sendMessage" | ...>` — `messages` is not available. `clearMessages` also does not exist; the correct name is `reset`.
- **Fix:** Switched to `useCopilotChatInternal` (exported from `@copilotkit/react-core`) which exposes `messages: Message[]` and `reset: () => void`.
- **Files modified:** `frontend/src/components/chat/chat-panel.tsx`
- **Verification:** TypeScript 0 errors; export function accesses `messages` correctly
- **Committed in:** `e6f13d7` (Task 1)

**2. [Rule 1 - Bug] `@copilotkit/shared` not resolvable as direct import — used local type**

- **Found during:** Task 1 (importing `Message` type for export serialization)
- **Issue:** `import type { Message } from '@copilotkit/shared'` caused `error TS2307: Cannot find module '@copilotkit/shared'`. The package is a transitive dependency in pnpm's virtual store, not a direct project dependency.
- **Fix:** Removed the import; defined a minimal local `ChatMessage` interface covering the fields used in the export serialization (`role`, `content`). Cast `messages` with `(messages as ChatMessage[])`.
- **Files modified:** `frontend/src/components/chat/chat-panel.tsx`
- **Verification:** TypeScript 0 errors
- **Committed in:** `e6f13d7` (Task 1)

**3. [Rule 1 - Bug] `onSubmitMessage` cannot cancel send — used custom `Input` for slash command interception**

- **Found during:** Task 1 (implementing slash commands)
- **Issue:** Plan proposed `onSubmitMessage={(message) => { if (handleSlashCommand(message)) return false; }}`. The actual `onSubmitMessage` type is `(message: string) => void | Promise<void>` — returning `false` has no effect; the message is already being sent when this callback fires.
- **Fix:** Replaced with a custom `SlashCommandInput` component passed as `Input` prop to `CopilotChat`. The custom Input owns the input state and only calls `onSend(text)` if the message is not a slash command.
- **Files modified:** `frontend/src/components/chat/chat-panel.tsx`
- **Verification:** `/new` starts new conversation without sending to agent; `/clear` resets messages without sending
- **Committed in:** `e6f13d7` (Task 1)

---

**Total deviations:** 3 auto-fixed (3 bugs — API surface mismatches between plan spec and installed version)
**Impact on plan:** All fixes necessary for TypeScript correctness and functional slash commands. No scope creep. The plan's intent was fully realized — only the implementation mechanism differed from the plan's suggestions.

## Issues Encountered

- **Alembic heads collision (expected):** Migration 004 needed `down_revision = "9754fd080ee2"` (the merge head from 02-03). The plan included a check step for this and the correct value was discovered via `.venv/bin/alembic heads`.
- **Migration applied via docker exec psql:** Consistent constraint from all previous migrations — `.env` not present on host, alembic CLI cannot load DATABASE_URL from settings. Same pattern as 001–003.

## User Setup Required

None — all backend and frontend dependencies are installed. No new environment variables required beyond what was configured in earlier phases.

The `/settings` page is accessible at `http://localhost:3000/settings` once the frontend dev server is running. Custom instructions are stored per-user in the `user_instructions` PostgreSQL table and injected into the master agent's system prompt on every conversation turn.

## Notes for Phase 3 (Custom Instructions Pattern for Sub-Agents)

| Item | Value |
|---|---|
| Internal helper | `get_user_instructions(user_id, session)` in `api/routes/user_instructions.py` |
| Call pattern | Import inside node function; use `current_user_ctx.get()` to get user_id; wrap in `async with async_session()` |
| Fallback | `LookupError` from `.get()` → skip gracefully (tests safe, no user context) |
| DB table | `user_instructions` — one row per user, `instructions TEXT`, `user_id UUID UNIQUE` |
| API endpoint | `PUT /api/user/instructions/` — update from /settings page; takes `{"instructions": "..."}` |
| System prompt injection | `SystemMessage(content=f"Additional user instructions...\n\n{custom_instructions}")` prepended to messages list |

Sub-agents in Phase 3 that generate user-facing output should call `get_user_instructions()` and respect the user's preferences (language, format, verbosity). The `current_user_ctx` contextvar is already set by `gateway/runtime.py` before graph invocation.

## Next Phase Readiness

**Phase 2 is complete.** All 5 plans executed:
- 02-01: LiteLLM proxy + `get_llm()` factory
- 02-02: LangGraph master agent + CopilotKit runtime
- 02-03: Short-term memory + conversation API
- 02-04: AES-256-GCM credential vault
- 02-05: Chat UI + custom instructions (this plan)

**Ready for Phase 3 (Sub-Agents + Memory Expansion):**
- CopilotKit streaming endpoint is live at `/api/copilotkit`
- Agent name `blitz_master` is established — sub-agents registered in gateway/runtime.py
- `BlitzState` extensible: add sub-agent-specific state fields
- `_route_after_master` conditional stub ready for Phase 3 routing edges
- Credential vault ready for OAuth token storage (Phase 3 OAuth callbacks)
- Custom instructions pattern established for sub-agent system prompts

---
*Phase: 02-agent-core-and-conversational-chat*
*Completed: 2026-02-25*
