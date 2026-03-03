# Phase 12: Unified Admin Desk - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

All artifact management consolidated at `/admin` — Config and Credentials tabs added, admin controls removed from `/settings`. The chat-only AI Builder at `/admin/create` is replaced with a split-panel hybrid: a structured form (left 45%) + an AI chat assistant (right 55%) with bidirectional state sync via the `fill_form` co-agent tool. Creating new agents, changing RBAC model, or adding new artifact types are out of scope.

</domain>

<decisions>
## Implementation Decisions

### AI ↔ Form field conflicts
- When the AI fills a field the user already typed in: **highlight the changed field** — brief pulse/flash animation so user notices the update; no confirmation required
- When AI suggests a name that's already taken: **fill it and let the user see the ✗ badge** — no special AI handling; user decides how to rename
- Form state syncs to AI context: **on every keystroke via co-agent state** — continuous sync using existing CopilotKit co-agent state rendering pattern
- When `fill_form` touches multiple fields at once: **all fields pulse simultaneously** — single animation frame, no stagger

### Settings migration
- `/settings/agents` → **redirect to `/admin/config`** (HTTP redirect, not 404)
- `/settings/integrations` → **redirect to `/admin/mcp-servers`** (HTTP redirect, not 404)
- `/settings` page Admin grid (2-column Agents + Integrations links): **remove entirely** — nothing replaces it; `/settings` becomes personal-only
- Non-admin users and MCP integrations: **admin-only** — non-admins cannot add/remove MCP servers; they consume registered servers only
- Credentials revoke UX: **optimistic update** — row disappears immediately on Revoke click; if DELETE fails, row reappears with an error toast

### Form validation
- Inline validation trigger: **on blur** — error appears when user leaves the field; no red borders while typing
- Submit button: **disabled until valid** — all required fields pass + name check returns available; Submit stays disabled during the name check in-flight
- Name check in-flight state: **spinner** replaces the ✓/✗ badge while the debounced request is pending
- POST failure (server error): **error toast at top-right** — "Failed to create artifact — try again"; form stays open with all values intact

### Wizard initial state
- Landing on `/admin/create` fresh: **type selector is prominent at top; form fields are visible but greyed out/disabled** until a type is selected
- AI initial message (fresh wizard): **instructional** — "I can create agents, tools, skills, and MCP servers. Just describe what you need."
- AI initial message (clone entry — `?clone_type=&clone_id=`): **context-aware** — "I've pre-filled from [artifact name]. Change anything or tell me what to adjust."
- After successful submit: **success toast + form resets to blank** — toast: "Agent created — view in Agents tab"; wizard stays on `/admin/create` for creating another artifact

### Claude's Discretion
- Exact pulse/flash animation duration and CSS for AI-filled fields
- Implementation of redirect (Next.js `redirect()` in page or middleware)
- Exact wording of the instructional AI greeting
- How `ArtifactBuilderState` tracks the clone source name for the context-aware greeting

</decisions>

<specifics>
## Specific Ideas

- The design doc (`docs/plans/2026-03-03-phase-12-unified-admin-desk-design.md`) contains the full approved layout — exact file names, API shapes, component structure. Planner should read it as the primary reference.
- Pulse animation on AI-filled fields: should feel like a subtle "ripple" — not distracting, just enough to catch attention (similar to how form autofill looks in browsers)
- The AI greeting is functional, not conversational — sets expectations clearly so the user knows exactly what to type

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 12-unified-admin-desk*
*Context gathered: 2026-03-03*
