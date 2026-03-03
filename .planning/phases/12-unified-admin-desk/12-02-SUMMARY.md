---
phase: 12-unified-admin-desk
plan: "02"
subsystem: admin-wizard
tags: [wizard, copilotkit, form, ai-assisted, artifact-builder, fill_form, check-name, clone]
dependency_graph:
  requires:
    - 12-01-SUMMARY.md (admin desk foundation, /admin routing)
    - backend/agents/artifact_builder.py (existing agent to extend)
  provides:
    - Hybrid split-panel artifact creation wizard at /admin/create
    - fill_form tool for AI-driven form field updates
    - check-name endpoints on all 4 artifact routes
    - ArtifactBuilderState form field tracking
    - Clone button on ArtifactTable and ArtifactCardGrid
  affects:
    - /admin/create (replaced pure-chat with split-panel wizard)
    - ArtifactTable (new artifactType prop + Clone button)
    - ArtifactCardGrid (new artifactType prop + Clone button)
tech_stack:
  added:
    - sonner (toast notifications — already in package.json)
    - langchain_core.tools.tool decorator for fill_form
  patterns:
    - useCoAgentStateRender for co-agent state → form field sync
    - CopilotKit.bind_tools(fill_form) for AI → form bidirectional sync
    - Next.js catch-all proxy pattern (existing) + dedicated [type]/check-name route
    - 300ms debounce for name availability check
    - Set<string> aiFilledFields + 1500ms pulse animation via useEffect
key_files:
  created:
    - frontend/src/components/admin/artifact-wizard.tsx
    - frontend/src/components/admin/artifact-wizard-form.tsx
    - frontend/src/components/admin/artifact-wizard-templates.tsx
    - frontend/src/components/admin/artifact-wizard-name-check.tsx
    - frontend/src/components/admin/clone-artifact-modal.tsx
    - frontend/src/app/api/admin/[type]/check-name/route.ts
  modified:
    - backend/agents/state/artifact_builder_types.py
    - backend/agents/artifact_builder.py
    - backend/api/routes/admin_agents.py
    - backend/api/routes/admin_tools.py
    - backend/api/routes/admin_skills.py
    - backend/api/routes/mcp_servers.py
    - frontend/src/app/admin/create/page.tsx
    - frontend/src/components/admin/artifact-table.tsx
    - frontend/src/components/admin/artifact-card-grid.tsx
    - backend/tests/agents/test_artifact_builder.py
decisions:
  - "[12-02]: bind_tools([fill_form]) called on get_llm() in gather_type and gather_details nodes — allows AI to update form fields from either node"
  - "[12-02]: fill_form tool returns summary string; actual state update done in _fill_form_node by reading tool_calls from last AIMessage"
  - "[12-02]: _route_intent checks for ToolMessage last message to route to fill_form_node — prevents infinite loop"
  - "[12-02]: ArtifactWizardTemplates imports FormState type from artifact-wizard-form — type-only import, no circular dep"
  - "[12-02]: check-name uses is_active filter for agents/tools/skills; McpServer has no is_active semantic filter (unique name enforced at DB level)"
  - "[12-02]: sonner toast used for success/error (already in package.json at 2.0.7)"
  - "[12-02]: pnpm build fails due to root-owned .next/types dir from prior Docker run — pre-existing infra issue, not code issue; tsc --noEmit passes with 0 errors"
metrics:
  duration: "10 min 16 sec"
  completed_date: "2026-03-03"
  tasks_completed: 3
  tasks_total: 3
  files_created: 6
  files_modified: 10
  backend_tests: 609
  typescript_errors: 0
---

# Phase 12 Plan 02: Hybrid Artifact Creation Wizard Summary

**One-liner:** Split-panel wizard at /admin/create with structured form (45%), AI chat (55%), fill_form co-agent tool for live form updates, debounced name-check, template cards, clone support, and permissions checklist.

## What Was Built

### Backend (Task 1)

**ArtifactBuilderState extensions** (`backend/agents/state/artifact_builder_types.py`):
- Added 11 form_* fields: `form_name`, `form_description`, `form_version`, `form_required_permissions`, `form_model_alias`, `form_system_prompt`, `form_handler_module`, `form_sandbox_required`, `form_entry_point`, `form_url`, `clone_source_name`

**fill_form tool** (`backend/agents/artifact_builder.py`):
- `@tool fill_form(...)` — 11 optional parameters, returns fill summary string
- `_fill_form_node` — extracts tool call args from last AIMessage, merges into form state, emits via `copilotkit_emit_state`
- `_route_intent` updated — detects `ToolMessage` as last message → routes to `fill_form_node`
- LLM in `_gather_type_node` and `_gather_details_node` now bound with `fill_form` tool
- `_emit_builder_state` updated to accept `form_updates` dict for emitting form field values

**check-name endpoints** (all 4 route files):
- `GET /api/admin/agents/check-name?name=...` → `{"available": bool}`
- `GET /api/admin/tools/check-name?name=...` → `{"available": bool}`
- `GET /api/admin/skills/check-name?name=...` → `{"available": bool}`
- `GET /api/admin/mcp-servers/check-name?name=...` → `{"available": bool}`
- Case-insensitive matching via `func.lower()` + `is_active` filter
- Declared BEFORE `/{id}` routes to prevent FastAPI routing collision

### Frontend (Tasks 2a + 2b)

**Leaf components** (Task 2a):
- `ArtifactWizardNameCheck` — controlled input with 300ms debounce, fetch to `/api/admin/{type}/check-name`, idle/checking/available/taken states
- `ArtifactWizardTemplates` — template cards for 7 hardcoded templates (2 agent, 2 tool, 2 skill, 1 mcp_server), `Partial<FormState>` defaults
- `CloneArtifactModal` — overlay modal with Zod-validated artifact list fetch, client-side search filter, Escape/backdrop close
- `/api/admin/[type]/check-name/route.ts` — Next.js proxy with ALLOWED_TYPES allowlist, next-auth JWT injection

**Form + shell** (Task 2b):
- `FormState` interface exported from `artifact-wizard-form.tsx` (name, description, version, model_alias, system_prompt, required_permissions, sandbox_required, handler_module, entry_point, url, auth_token)
- `ArtifactWizardForm` — 6-section form: type selector (4 radio buttons), start-from shortcuts (blank/clone/templates), common fields (name+check, description, version), type-specific fields, JSON preview, cancel/submit actions
- Permissions field is a multi-select checklist (12 known permissions) — no free-text
- `ArtifactWizard` — top-level shell wrapping `CopilotKit` + `WizardInner`, reads `?clone_type` + `?clone_id` URL params, pre-fills from clone source API, `useCoAgentStateRender` watches `artifact_builder` state for form_* fields with 100ms polling interval, tracks `aiFilledFields: Set<string>` for 1500ms pulse animation
- `/admin/create/page.tsx` — replaced `ArtifactBuilderClient` with `ArtifactWizard`
- `ArtifactTable` — added `artifactType` prop + Clone button (`router.push(/admin/create?clone_type=X&clone_id=Y)`)
- `ArtifactCardGrid` — added `artifactType` prop + Clone button

## Verification Results

- Backend tests: **609 passed, 1 skipped** (same count as baseline)
- TypeScript strict: **0 errors** (`pnpm exec tsc --noEmit`)
- All 8 key files confirmed to exist on disk

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test mocks to handle `.bind_tools()` chaining**
- **Found during:** Task 1 verification — 3 tests failed after adding `.bind_tools([fill_form])` to `get_llm()` calls
- **Issue:** Existing `_gather_details_node` and `_gather_type_node` tests patched `get_llm()` to return `mock_llm` with `ainvoke` set, but `get_llm().bind_tools([fill_form])` returned a new MagicMock without `ainvoke` configured
- **Fix:** Added `mock_llm.bind_tools.return_value = mock_llm` to 5 affected tests
- **Files modified:** `backend/tests/agents/test_artifact_builder.py`
- **Commit:** 693c72e

### Known Pre-existing Issues (Not Fixed)

**1. Root-owned `.next/types` directory prevents `pnpm run build`**
- **Issue:** `.next/types/` owned by root from prior Docker-run `next build`; `unlink` fails with EACCES
- **Impact:** `pnpm run build` fails with permission error; `pnpm exec tsc --noEmit` passes with 0 errors
- **Resolution:** Requires `sudo rm -rf .next/types` (no sudo terminal in GSD context) — pre-existing infra issue
- **Canonical TypeScript check passes** — no code errors

## Checkpoint

**Task 3 is a `checkpoint:human-verify`** — execution pauses here for human validation of the /admin/create wizard end-to-end.

**2. [Rule 1 - Bug] Fixed test assertion for redesigned agent prompt**
- **Found during:** Post-approval final verification
- **Issue:** `test_get_system_prompt_contains_schema_fields` checked for `routing_keywords` and `handler_module` in agent prompt; these were removed in commit `9271c73` (prompt rewritten to focus on fill_form fields for the hybrid wizard)
- **Fix:** Updated assertion to check `model_alias` and `system_prompt` instead — the actual fields the new agent prompt documents
- **Files modified:** `backend/tests/agents/test_artifact_builder.py`
- **Commit:** 0a4a33b

## Self-Check: PASSED

All 8 declared files found on disk. All commits exist in git (693c72e, 2b8a76d, 12e8356, 557df5d, 0a4a33b). Backend 609 tests passing. TypeScript 0 errors.
