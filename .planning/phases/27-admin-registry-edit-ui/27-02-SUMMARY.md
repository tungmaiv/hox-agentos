---
phase: 27-admin-registry-edit-ui
plan: 02
subsystem: ui
tags: [react, zod, tailwind, forms, admin, registry]

# Dependency graph
requires:
  - phase: 27-admin-registry-edit-ui
    plan: 01
    provides: RegistryDetailLayout, StickySaveBar, Zod schemas, validateField helper
provides:
  - Agent detail page at /admin/agents/[id] with Overview, Config, Permissions tabs
  - Tool detail page at /admin/tools/[id] with Overview, Config, Permissions tabs
  - Form-based editing for agent system prompt, model alias, routing keywords
  - Form-based editing for tool handler type with conditional field visibility
affects: [27-03, admin-permissions-ui]

# Tech tracking
tech-stack:
  added: []
  patterns: [registry-detail-form-pattern, conditional-field-visibility, config-merge-on-save]

key-files:
  created:
    - frontend/src/app/(authenticated)/admin/agents/[id]/page.tsx
    - frontend/src/app/(authenticated)/admin/tools/[id]/page.tsx
  modified: []

key-decisions:
  - "Agent handler module/function are read-only on detail page -- code-level changes require redeployment"
  - "Tool handler type change auto-sets sandbox_required when switching to sandbox mode"

patterns-established:
  - "Detail page form: buildFormData extracts config fields, formToPayload merges back with original config"
  - "Conditional visibility: handler_type drives which config fields are shown/hidden"
  - "Save flow: full Zod safeParse before PUT, inline errors on failure, success toast on save"

requirements-completed: [REG-01, REG-02, REG-03]

# Metrics
duration: 4min
completed: 2026-03-15
---

# Phase 27 Plan 02: Agent & Tool Detail Pages Summary

**Agent and tool detail pages with tabbed form editing, Zod validation on blur, and conditional field visibility based on handler type**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-15T12:55:54Z
- **Completed:** 2026-03-15T12:59:34Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created agent detail page with Overview (read-only ID/name + editable display name/description/status), Config (system prompt textarea, model alias dropdown, routing keywords, read-only handler info), and Permissions tabs
- Created tool detail page with conditional field visibility: backend/sandbox shows handler module/function, MCP shows tool name/server ID
- Both pages use RegistryDetailLayout with sticky save bar, beforeunload guard, and Zod validation on blur
- Save logic merges form fields back into original config object before PUT to /api/registry/{id}

## Task Commits

Each task was committed atomically:

1. **Task 1: Agent detail page with form editing** - `b5d14a9` (feat)
2. **Task 2: Tool detail page with form editing** - `9e798e6` (feat)

## Files Created/Modified
- `frontend/src/app/(authenticated)/admin/agents/[id]/page.tsx` - Agent detail with 3 tabs, system prompt/model alias/routing keywords editing
- `frontend/src/app/(authenticated)/admin/tools/[id]/page.tsx` - Tool detail with 3 tabs, handler type conditional fields, schema editors

## Decisions Made
- Agent handler module and function are read-only on the detail page -- these are code-level concerns that require redeployment, not admin UI changes
- Tool handler type change to "sandbox" auto-sets the sandbox_required checkbox for convenience

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `pnpm run build` fails due to pre-existing EACCES permission on .next/trace (Docker ownership issue, same as Plan 01) -- TypeScript check passes cleanly

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Agent and tool detail pages complete, ready for Plan 03 (MCP server + skill detail pages)
- Established form editing pattern (buildFormData/formToPayload) can be replicated for remaining types

---
*Phase: 27-admin-registry-edit-ui*
*Completed: 2026-03-15*
