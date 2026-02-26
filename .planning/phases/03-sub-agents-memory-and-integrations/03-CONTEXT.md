# Phase 3: Sub-Agents, Memory, and Integrations - Context

**Gathered:** 2026-02-26
**Status:** Ready for planning

<domain>
## Phase Boundary

The agent can perform real work — fetch email, check calendars, query CRM, remember user preferences across sessions — making it genuinely useful for daily routines. This phase delivers sub-agents (email, calendar, project), 3-tier memory with embeddings, MCP framework, and A2UI rich UI components. Canvas workflows, Telegram/WhatsApp channels, and full agent authoring are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Sub-agent status in chat
- Use CopilotKit's built-in tool call panel visualization (not custom indicators)
- Panel shows tool name + status only (e.g., "Calendar Agent ✓") — no inputs/outputs exposed to user
- Panel is collapsed by default; user can expand to see agent name and status
- Master agent emits a brief intent statement before delegating: "Let me check your calendar for today."
- Multiple sub-agents in one turn: sequential panels, one after another as each completes
- Sub-agent failure: master agent informs user what failed and continues with whatever is available ("I couldn't reach the CRM, but here's your calendar...")
- Chat input is disabled while agent is running (no queuing, no cancel-and-restart)

### A2UI card content
- **CalendarCard:** Default view shows title + time range + conflict indicator. Expandable to full detail: title, time, location, attendees, conflict description.
- **EmailSummaryCard:** Default per-item shows sender + subject + 1-line AI summary. Expandable to: full AI summary + timestamp + Reply button (stub) + Archive button (stub). Shows 5 emails by default with "Show more" for additional.
- **ProjectStatusWidget:** Default shows project name + status badge + progress bar (% complete) + open tasks count + last updated timestamp. Expandable to: full kanban board with drag-and-drop between columns, syncing task moves back to CRM via MCP tool call.
- **Fallback rendering (plain text responses):** User-selectable preference in Settings → Chat Preferences. Options: Markdown (default), Card-wrapped (all responses in card container), Inline chips (entity detection). Default: Markdown.
- **Refresh button:** Each card has a refresh icon that triggers a new sub-agent call for that data source.
- Reply/Archive buttons on EmailSummaryCard are stubs in Phase 3 (real OAuth wired in a later phase).
- Kanban drag-and-drop in ProjectStatusWidget is interactive in Phase 3 — task moves call MCP `crm.update_task_status`.

### Memory behavior
- **Fact extraction:** Automatic from all conversations — agent infers facts (preferences, patterns, stated info) without requiring explicit "remember that..." statements.
- **Memory citation:** Silent use — agent uses facts naturally without mentioning they came from memory.
- **Conflict resolution:** Use most recent fact; mark old conflicting fact as superseded in DB (soft delete, not hard delete).
- **Episode summaries:** Triggered after every 10 conversation turns (configurable via `system_config` key `memory.episode_turn_threshold`).
- **Semantic search retrieval:** Top 5 facts by cosine similarity injected into agent context per request.
- **Fact lifetime:** Facts persist indefinitely (no TTL). Deleted only when user explicitly removes them.
- **Settings → Memory page:** Per-user page (not admin-only) where users can view stored facts and episode summaries, delete individual facts, and clear all memory.

### Disabled agent UX
- When a user requests a disabled agent's capability, master agent responds: "Email access isn't available right now. Contact your admin." (friendly, no hard error).
- Settings → Agents page: admin-only. Shows each agent with a toggle + status badge (Active / Disabled) and agent description.
- Regular users cannot see Settings → Agents.
- No notification to users when an agent is re-enabled — it silently becomes available again.

### Settings pages introduced in Phase 3
- **Settings → Agents** (admin-only): toggle + status badge per agent
- **Settings → Integrations** (admin-only): MCP server CRUD — add/remove/list servers, connection status
- **Settings → Memory** (per-user): view facts + episodes, delete individual, clear all
- **Settings → Chat Preferences** (per-user): response rendering style (Markdown / Card-wrapped / Inline chips)

### Channel sub-agent: DeliveryRouterNode (outbound delivery)
- The "channel sub-agent" is **not** a full LangGraph sub-agent — it is a deterministic `DeliveryRouterNode` added at the end of the master agent graph (no LLM calls).
- Responsibility: take the agent's formatted response and route it to one or more `DeliveryTarget`s.
- `DeliveryTarget` enum defined in Phase 3: `WEB_CHAT` (active), `EMAIL_NOTIFY` (stub), `TELEGRAM` (stub), `TEAMS` (stub).
- Phase 3 only `WEB_CHAT` actually delivers. Other targets log a warning and no-op.
- Stubs are registered so Phase 4 canvas workflow nodes can set `delivery_targets` in their output spec before Phase 5 adapters exist.
- Phase 5 ChannelAdapter implementations plug into the same `deliver(target, payload)` interface without changing agent graph.
- This is distinct from Phase 5 ChannelAdapter (inbound): DeliveryRouterNode = outbound; ChannelAdapter = inbound.

### A2UI interactive tool calls: `useMcpTool` hook + `POST /api/tools/call`
- All interactive actions from A2UI components (kanban drag-and-drop, card refresh, email archive stub, etc.) use a single `useMcpTool<TParams, TResult>(toolName)` React hook.
- The hook calls `POST /api/tools/call` on the Next.js proxy, which forwards to `POST /api/tools/call` on the backend.
- The backend endpoint enforces all 3 security gates (JWT → RBAC → Tool ACL) and executes the tool directly via `tool_registry.execute()` — synchronous request/response (not SSE streaming, no LangGraph overhead).
- This is the **universal standard** for all UI-initiated tool/MCP calls. No component calls `fetch` directly.
- `useMcpTool` returns `{ call, isLoading, error }` — consistent across all cards and widgets.

### Claude's Discretion
- Exact visual styling of tool call panels (colors, icons, animations)
- Kanban board column layout and card styling
- Exact wording of friendly messages for disabled/unavailable agents
- Loading skeleton designs for cards while sub-agent is running
- Episode summary prompt wording and fact extraction prompt wording
- How conflict detection determines "most recent" when timestamps are identical

</decisions>

<specifics>
## Specific Ideas

- CalendarCard: expand/collapse pattern (show title+time by default, click to see full detail including attendees and conflicts)
- ProjectStatusWidget: kanban board is interactive with drag-and-drop in Phase 3 (ambitious scope — MCP `crm.update_task_status` must exist in CRM mock)
- EmailSummaryCard Reply/Archive are stubs now, real actions in a later phase
- Settings → Chat Preferences: three rendering modes user-selectable, default Markdown
- Memory facts page should feel like a "data about me" transparency page — user-friendly, not technical

</specifics>

<deferred>
## Deferred Ideas

- Real Gmail / Google Calendar OAuth flows — deferred to later phase (Phase 3 uses mock data)
- Telegram/WhatsApp/Teams ChannelAdapter (inbound) — Phase 5. The outbound DeliveryRouterNode with stubs is built in Phase 3.
- Full agent authoring UI (beyond enable/disable) — Phase 6 (Extensibility Registries)
- Switching embedding models via UI — post-MVP (pgvector dimension lock makes this a migration, not a toggle)
- Auto-refresh with TTL for cards — noted for later (user opted for manual refresh icon instead)
- Admin announcement when re-enabling agents — noted for later

</deferred>

---

*Phase: 03-sub-agents-memory-and-integrations*
*Context gathered: 2026-02-26*
