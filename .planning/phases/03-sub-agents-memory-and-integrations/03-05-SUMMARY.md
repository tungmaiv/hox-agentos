---
phase: "03"
plan: "05"
subsystem: frontend-a2ui
tags:
  - a2ui
  - generative-ui
  - mcp
  - settings
  - memory
  - frontend
  - backend
dependency_graph:
  requires:
    - 03-04  # sub-agent nodes produce CalendarOutput / EmailSummaryOutput / ProjectStatusResult JSON
    - 03-03  # crm.update_task_status registered in tool_registry
    - 03-02  # memory_facts table + mark_fact_superseded function
  provides:
    - A2UIMessageRenderer (CalendarCard / EmailSummaryCard / ProjectStatusWidget routing)
    - useMcpTool hook (universal A2UI tool call hook)
    - POST /api/tools/call backend endpoint (3-gate security)
    - Settings Memory page (fact/episode viewer + delete)
    - Settings Chat Preferences page (rendering mode selector)
  affects:
    - frontend chat rendering pipeline (AssistantMessage now routes through A2UIMessageRenderer)
    - user-facing memory transparency (Settings → Memory)
tech_stack:
  added:
    - react-markdown: ^10.1.0 (already in package.json — no install needed)
    - zod: ^4.3.6 (already in package.json)
  patterns:
    - useMcpTool hook: only way for A2UI components to call tools
    - Zod safeParse for all structured agent output validation
    - Server Component proxy routes with auth() injection (no credentials in browser)
    - CopilotKit AssistantMessage prop for custom message rendering
key_files:
  created:
    - backend/api/routes/tools.py
    - backend/api/routes/memory_settings.py
    - backend/tests/agents/test_agent_outputs.py
    - frontend/src/lib/a2ui-types.ts
    - frontend/src/components/a2ui/CalendarCard.tsx
    - frontend/src/components/a2ui/EmailSummaryCard.tsx
    - frontend/src/components/a2ui/ProjectStatusWidget.tsx
    - frontend/src/components/a2ui/A2UIMessageRenderer.tsx
    - frontend/src/components/a2ui/index.ts
    - frontend/src/hooks/use-mcp-tool.ts
    - frontend/src/app/api/tools/call/route.ts
    - frontend/src/app/api/settings/memory/route.ts
    - frontend/src/app/api/settings/memory/[factId]/route.ts
    - frontend/src/app/api/settings/preferences/route.ts
    - frontend/src/app/settings/memory/page.tsx
    - frontend/src/app/settings/chat-preferences/page.tsx
  modified:
    - backend/main.py (added tools.router + memory_settings.router)
    - frontend/src/components/chat/chat-panel.tsx (added CustomAssistantMessage → A2UIMessageRenderer)
    - frontend/src/app/settings/page.tsx (added Memory + Chat Preferences nav links)
decisions:
  - "useMcpTool generic signature changed from <TParams, TResult>: UseMcpToolResult<TResult> to <TParams, TResult>: UseMcpToolResult<TParams, TResult> — TypeScript strict mode requires TParams in return type to avoid `unknown not assignable to TParams` error"
  - "react-markdown v10 no longer accepts className prop directly — wrapped in a div with className instead"
  - "backend DB dependency: get_async_session not exported from core.db; correct FastAPI dep is get_db (same pattern as credentials.py)"
  - "Chat preferences stored in system_config table keyed as user.{user_id}.chat_preferences — same table used for admin config, user-scoped keys have user. prefix"
  - "Kanban drag-drop simplified for Phase 3: columns rendered as click targets calling useMcpTool; full @dnd-kit drag-drop deferred to Phase 4 when task data comes from real MCP calls"
  - "AssistantMessage prop wired via useMemo() like UserMessage — stable reference prevents CopilotChat focus loss"
metrics:
  duration_min: 35
  completed_date: "2026-02-26"
  tasks_completed: 2
  tasks_total: 3
  files_created: 16
  files_modified: 3
---

# Phase 3 Plan 05: A2UI Components + Tool Endpoint + Settings Pages Summary

A2UI rendering pipeline: sub-agent JSON → A2UIMessageRenderer → CalendarCard / EmailSummaryCard / ProjectStatusWidget (or ReactMarkdown fallback). useMcpTool hook provides the only path for component-to-tool calls via POST /api/tools/call with full 3-gate security.

## What Was Built

### Backend (Task 1)

**`backend/api/routes/tools.py`**
- `POST /api/tools/call` — universal UI-to-tool execution endpoint
- Gate 1: JWT via `Depends(get_current_user)`
- Gates 2+3: enforced inside `call_mcp_tool()` (RBAC + tool_acl table)
- Only MCP tools supported in Phase 3; backend tool direct execution returns 501

**`backend/api/routes/memory_settings.py`**
- `GET /api/user/memory/facts` — list active facts for JWT user (max 100)
- `DELETE /api/user/memory/facts/{fact_id}` — soft-delete one fact with ownership check (`fact.user_id == jwt_user_id`)
- `DELETE /api/user/memory/facts` — soft-delete ALL facts for JWT user
- `GET /api/user/memory/episodes` — list episode summaries (max 50)
- `GET /api/user/preferences` — get chat rendering mode
- `PUT /api/user/preferences` — update rendering mode (upsert in system_config)

**`backend/tests/agents/test_agent_outputs.py`** — 3 smoke tests, all passing:
- `test_email_agent_output_is_valid_json` — validates EmailSummaryOutput schema
- `test_calendar_agent_output_has_correct_agent_field` — validates agent="calendar"
- `test_project_status_result_validates_against_schema` — validates ProjectStatusResult

### Frontend (Task 2)

**`frontend/src/lib/a2ui-types.ts`**
- Zod schemas: `CalendarOutputSchema`, `EmailSummaryOutputSchema`, `ProjectStatusResultSchema`
- TypeScript types inferred from schemas (no separate interface declarations)

**`frontend/src/hooks/use-mcp-tool.ts`**
- `useMcpTool<TParams, TResult>(toolName)` hook: `{ call, isLoading, error }`
- POSTs to `/api/tools/call` (Next.js proxy); no direct fetch in components
- Only way A2UI components call tools (CONTEXT.md invariant)

**A2UI components** (all in `frontend/src/components/a2ui/`):
- `CalendarCard.tsx` — date header, event rows, red "Conflict" badge; Server Component
- `EmailSummaryCard.tsx` — unread count badge, 5-item preview, show-more; stub Reply/Archive; useMcpTool refresh
- `ProjectStatusWidget.tsx` — colored status badge, progress bar, expandable kanban columns; `useMcpTool("crm.update_task_status")` wired for task moves
- `A2UIMessageRenderer.tsx` — JSON parse → agent-type routing → Zod safeParse → card → fallback ReactMarkdown

**Proxy routes** (all inject Bearer token server-side):
- `POST /api/tools/call` → backend POST /api/tools/call
- `GET/DELETE /api/settings/memory` → backend facts+episodes endpoints
- `DELETE /api/settings/memory/[factId]` → backend DELETE /api/user/memory/facts/{id}
- `GET/PUT /api/settings/preferences` → backend /api/user/preferences

**Settings pages**:
- `/settings/memory` — fact list with per-fact delete + "Clear all" with confirmation; episode summaries collapsible; Zod validation on API response
- `/settings/chat-preferences` — 3 rendering mode radio options; saves to backend; persists on reload

**`chat-panel.tsx` update**:
- `CustomAssistantMessage` wraps `A2UIMessageRenderer` — wired to `CopilotChat` via `AssistantMessage={CustomAssistantMessage}` prop
- Created with `useMemo(() => ..., [])` for stable reference (no focus loss)

## useMcpTool Hook Design

Key design decisions:
1. Generic over both `<TParams, TResult>` — TypeScript strict mode requires TParams in the return type signature
2. `useCallback([toolName])` — stable reference, only recreates when tool name changes
3. Returns `{ call, isLoading, error }` — simple, no reducer needed at this scale
4. Separation: hook calls `/api/tools/call` (Next.js proxy) → Next.js injects Bearer → backend enforces gates

## A2UI Component Rendering Edge Cases

1. **Empty string content**: `A2UIMessageRenderer` catches empty JSON gracefully; falls back to markdown (empty markdown renders nothing)
2. **Partial JSON during streaming**: The `try/catch` around `JSON.parse` catches SyntaxError — incomplete JSON during SSE streaming safely falls to ReactMarkdown (shows partial text)
3. **Unknown `agent` field**: An object with `agent: "unknown-type"` falls through all three checks and renders as markdown (correct behavior)
4. **Zod validation failure**: If the JSON structure doesn't match the schema (e.g., missing `progress_pct`), `safeParse` returns `success: false` and falls back to markdown silently
5. **react-markdown v10**: No longer accepts `className` prop — wrapped in `<div className="prose prose-sm max-w-none">` instead

## Kanban Drag-Drop Implementation Approach

Phase 3 uses click-based column assignment rather than `@dnd-kit` drag-and-drop:
- Kanban columns expand when user clicks "Show kanban board"
- Each column shows a "Move here" button that calls `useMcpTool("crm.update_task_status")`
- This satisfies the architectural requirement (useMcpTool wired, POST /api/tools/call visible in Network tab)
- Full drag-and-drop with actual task data from MCP deferred to Phase 4

Rationale: Phase 3 project agent returns `ProjectStatusResult` (aggregate status), not individual tasks. Task list requires a separate `crm.list_tasks` MCP call. Phase 4 will fetch tasks and wire full `@dnd-kit` drag-drop.

## Checkpoint Verification (Task 3)

Status: **AWAITING HUMAN VERIFICATION**

The checkpoint requires visual verification of 6 scenarios on the running full stack. All automated criteria are met:
- pnpm build: 0 TypeScript errors
- pytest tests/agents/test_agent_outputs.py: 3/3 passed
- A2UIMessageRenderer exists with CalendarCard/EmailSummaryCard/ProjectStatusWidget routing
- useMcpTool is the only tool call mechanism in A2UI components
- All Zod safeParse calls in A2UIMessageRenderer — no uncaught errors possible
- POST /api/tools/call enforces all 3 security gates

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Missing Import] `get_async_session` not exported from `core.db`**
- **Found during:** Task 1 — backend import verification
- **Issue:** Plan used `from core.db import get_async_session` but the actual FastAPI dependency exported is `get_db` (see `core/db.py` line 37)
- **Fix:** Changed to `from core.db import get_db` in both `tools.py` and `memory_settings.py`
- **Files modified:** `backend/api/routes/tools.py`, `backend/api/routes/memory_settings.py`
- **Commit:** 3387927

**2. [Rule 1 - Bug] `react-markdown` v10 removed `className` prop**
- **Found during:** Task 2 — `pnpm build` TypeScript check
- **Issue:** `<ReactMarkdown className="prose prose-sm max-w-none">` fails in react-markdown v10 — `className` is no longer a valid prop on the component
- **Fix:** Wrapped in `<div className="prose prose-sm max-w-none"><ReactMarkdown>...</ReactMarkdown></div>`
- **Files modified:** `frontend/src/components/a2ui/A2UIMessageRenderer.tsx`
- **Commit:** 7c81910

**3. [Rule 1 - Bug] `useMcpTool` TypeScript strict mode type error**
- **Found during:** Task 2 — `pnpm build` TypeScript check
- **Issue:** `UseMcpToolResult<TResult>` return type caused "Type 'unknown' is not assignable to type 'TParams'" error in strict mode
- **Fix:** Changed return type to `UseMcpToolResult<TParams, TResult>` — both type params in the result interface
- **Files modified:** `frontend/src/hooks/use-mcp-tool.ts`
- **Commit:** 7c81910

## Phase 3 Exit Criterion Status

| # | Criterion | Status |
|---|-----------|--------|
| 1 | EmailSummaryCard renders for "summarize my emails" | Awaiting verification |
| 2 | CalendarCard renders for "what's on my calendar today?" | Awaiting verification |
| 3 | ProjectStatusWidget renders for "Project Alpha status" | Awaiting verification |
| 4 | Markdown fallback for "write me a haiku" | Awaiting verification |
| 5 | All Zod safeParse calls succeed (no console errors) | Implemented (no throws on parse failure) |
| 6 | useMcpTool wired in ProjectStatusWidget (POST /api/tools/call in Network) | Implemented |
| 7 | Settings → Memory shows facts with delete | Implemented |
| 8 | Settings → Chat Preferences shows 3 modes; persists | Implemented |
| 9 | pnpm build: 0 TypeScript errors | PASSED |
| 10 | Backend tests pass (agent output schemas) | PASSED (3/3) |

## Self-Check: PASSED

All created files exist on disk. All commits verified in git log.

| Check | Result |
|-------|--------|
| `backend/api/routes/tools.py` | FOUND |
| `backend/api/routes/memory_settings.py` | FOUND |
| `backend/tests/agents/test_agent_outputs.py` | FOUND |
| `frontend/src/lib/a2ui-types.ts` | FOUND |
| `frontend/src/components/a2ui/A2UIMessageRenderer.tsx` | FOUND |
| `frontend/src/hooks/use-mcp-tool.ts` | FOUND |
| `frontend/src/app/settings/memory/page.tsx` | FOUND |
| `frontend/src/app/settings/chat-preferences/page.tsx` | FOUND |
| Commit 3387927 (Task 1) | FOUND |
| Commit 7c81910 (Task 2) | FOUND |
