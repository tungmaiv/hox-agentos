# Phase 25: Skill Builder Tool Resolver - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Insert a `resolve_tools` LangGraph node into the artifact_builder graph (procedural skills only). This node maps each workflow step to a verified tool from the live registry, replacing the hardcoded tool list and LLM-guessed tool names. Skills with unresolved tool gaps are saved as `draft` and blocked from activation. When the missing tool is later created, the system auto-detects the resolution and promotes the skill to `pending_activation`. Admin reviews and manually activates.

Instructional skills, MCP tool resolution, and a full database-backed notification system are out of scope.

</domain>

<decisions>
## Implementation Decisions

### Builder chat gap output

- Gap summary is rendered as a **structured card** (distinct visual component, bordered/boxed), not inline chat text
- Tone: **actionable and forward-looking** — "Saved as draft. Next: build the missing tool in Tool Builder, then return here to activate."
- **All steps shown** (both resolved ✅ and missing ⚠️) — not just gap steps
- Missing tool label uses **plain language**: "No tool found for: send Slack message" (not "MISSING:send-slack-message")
- Each gap also shows a **suggested tool name** for auto-resolution: "Suggested name: `send-slack-message`"

### Skills list UX (pending_activation)

- `pending_activation` status: **amber badge + inline "Activate" button** directly in the table row (no need to navigate to detail page)
- `draft` skills with gaps: **grey badge + tooltip on hover** showing "X unresolved tool gap(s)" — no new columns
- Activate action: **no confirmation dialog** — admin action is intentional
- List default sort: **unchanged** — amber badge provides sufficient visual signal; no reorder or filter tab added

### Admin notification on auto-promotion

- When a tool is created and resolves skill gaps, the **tool creation success message** mentions the unblocked skills: "Tool created. 1 skill (daily-standup) moved to pending activation."
- Admin UI: **simple query-based bell icon** in admin nav showing count of `pending_activation` skills. Clicking opens a dropdown list. No separate notifications table — live query only.
- Bell covers **skills needing attention** (pending_activation) for MVP scope

### Slug matching

- **Strict substring match**: new tool's name must contain the gap's suggested slug as a substring (e.g., tool name `send-slack-message` resolves `MISSING:send-slack-message`)
- If admin named their tool differently: **manual gap clear via skill detail page** — admin picks the actual tool from a dropdown to resolve each gap explicitly
- **Partial gap resolution stays as draft** — all gaps must be resolved before promotion to `pending_activation`

### Claude's Discretion

- Exact card styling (border color, padding, icon sizes) for the gap summary block
- Exact dropdown UI for manual gap resolution in skill detail page
- Bell icon placement and popover layout in admin nav

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets

- `backend/agents/artifact_builder.py`: `_fetch_tool_reference_block()` already fetches active tools from registry — reuse as input to `resolve_tools` node
- `backend/agents/artifact_builder.py`: `_route_intent()` already handles conditional routing — add procedural-skill branch here
- `backend/registry/handlers/skill_handler.py`: `on_create()` already runs security scan — add tool_gaps draft enforcement here
- `backend/registry/handlers/tool_handler.py`: `on_create()` exists as a no-op log — implement gap auto-resolution here
- `backend/api/routes/registry.py`: `PATCH /{id}/status` activation endpoint exists — add tool_gaps gate here
- `frontend/src/app/(authenticated)/admin/skills/page.tsx`: skills list already has status badges — add amber `pending_activation` badge and inline Activate button

### Established Patterns

- LangGraph nodes: `async def _node_name(self, state: ArtifactBuilderState, config: RunnableConfig)` pattern used by all existing nodes
- Registry handlers: `on_create(entry, session)` async pattern, called from `UnifiedRegistryService.create_entry()`
- `blitz/fast` alias for bounded matching tasks (lower latency) — use for `resolve_tools` node
- Structured card output: builder already uses `validate_and_present` node that formats output — gap card should follow same markdown-fenced block pattern

### Integration Points

- `ArtifactBuilderState` (TypedDict in `artifact_builder_types.py`) — add `resolved_tools: list[dict]` and `tool_gaps: list[dict]` fields
- `RegistryEntry.config` JSONB — add `tool_gaps` array field when saving procedural skills
- `PATCH /api/registry/{id}/status` — add `tool_gaps` check before allowing `active` transition
- Admin nav bell: new component in admin layout that queries `GET /api/registry?type=skill&status=pending_activation` count

</code_context>

<specifics>
## Specific Ideas

- Gap card format: "Saved as DRAFT — N unresolved tool gap(s)" as header, then per-step list with ✅/⚠️ icons, then a clear next-step prompt
- Suggested tool name shown inline with each gap: "No tool found for: send Slack message · Suggested name: `send-slack-message`"
- Tool creation confirmation API response should include `unblocked_skills: [{id, name}]` so frontend can display the unblocked skills message
- Manual gap resolution UI: in skill detail page, each gap row has a "Resolve" dropdown listing active tools + a "Clear Gap" button

</specifics>

<deferred>
## Deferred Ideas

- **Full notification system** — Database-backed notifications with read/unread state, timestamps, dismissal, all admin action items. Significant standalone feature. Add as Phase 26 or backlog item.
- **Fuzzy/semantic slug matching** — LLM-assisted gap matching to handle name variations. Design doc notes this as a post-MVP upgrade path.
- **MCP tool resolution** — Same resolve_tools pattern applied to MCP tools. Deferred per design doc.
- **Re-run resolver on existing skills** — Admin-triggered re-resolution on draft skills. Useful when registry changes but skill was already created. Post-MVP.

</deferred>

---

*Phase: 25-skill-builder-tool-resolver*
*Context gathered: 2026-03-13*
