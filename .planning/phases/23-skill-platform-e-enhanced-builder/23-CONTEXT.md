# Phase 23: Skill Platform E — Enhanced Builder - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

The artifact builder gains three new capabilities: (1) generating full, executable skill content (procedure_json, instruction_markdown, Python handler stubs — not just metadata), (2) similar skill discovery from cached external repo indexes with fork-into-draft, (3) a mandatory security gate (SecurityScanner + SecurityReportCard) that runs on every Save before activation.

Claude Code skill import (YAML → agentskills.io adapter) is included as a builder source type.

ZIP import is already implemented (`POST /api/admin/skills/import/zip`, `SkillImporter.import_from_zip()`) — no new ZIP backend work needed.

Skill sharing, export, and SecurityScanner scoring factors are separate phases (done in 21–22).

</domain>

<decisions>
## Implementation Decisions

### Skill generation depth (SKBLD-01, 02, 03)

- **One-shot full scaffold:** When admin describes a skill goal, the AI generates a complete `procedure_json` (steps, tool references, prompt templates) or `instruction_markdown` in a single response. No step-by-step interactive interrogation.
- **Refinement:** Chat-first by default (user says "add a step to filter by sender" → AI updates draft in place). A **"Edit JSON" toggle** in the preview panel lets technical admins drop to raw JSON editing on demand. Both modes coexist.
- **Tool handler stub (SKBLD-03):** For tool-type artifacts, AI generates a **full Python stub**: function signature, `InputModel`/`OutputModel` Pydantic classes, docstring with usage notes, and a `# TODO: implement` comment in the body.
- **Stub delivery:** Stub is **auto-registered as a pending tool** in the DB. A new `handler_code TEXT` column on `tool_definitions` stores the stub text. Tool status = `pending_stub`. Admin edits and registers via the existing tool management flow.

### Similar skills discovery & fork (SKBLD-04, 05)

- **Trigger:** Dedicated **"Find Similar" button** in the right-side preview panel. Not proactive. Admin clicks when ready.
- **Similarity strategy:** pgvector cosine similarity on embedded name + description of the draft, searched against pre-embedded `skill_repo_index` entries. Reuses bge-m3 embedding pipeline. Returns top 3–5 results.
- **Fork behavior:** Forking an external skill **replaces the current draft in the same builder session**. The builder's existing `ArtifactBuilderState` is populated with the forked skill's full content (name, description, procedure_json/instruction_markdown, tags, category, allowed_tools).
- **Fork attribution:** `source_type='imported'`, plus a note in the draft (e.g., `forked_from: "skill-name@source-url"`). Carries through to the saved skill definition for security audit trail.

### Import sources & Claude Code skill import (Phase 21 deferred)

- **Builder "Fork/Import" panel** (new section in the right preview panel) has three import tabs:
  1. **AgentSkills URL** — existing URL import behavior
  2. **Claude Code GitHub URL** — fetches raw GitHub URL, applies format adapter (Claude Code YAML + markdown → agentskills.io fields)
  3. **ZIP upload** — triggers existing `POST /api/admin/skills/import/zip` endpoint (already implemented)
- **Claude Code adapter:** Maps Claude Code skill format fields:
  - `name` → `name`
  - `description` → `description` + seed `instruction_markdown`
  - Any tool references in content → attempt to map to known tool names
  - Category: guessed from content, admin can override
  - Result is a fork-ready draft in the builder for AI-assisted adaptation
- **Input sources for Claude Code:** Both GitHub raw URL fetch AND paste raw YAML content (tab-switcher in import panel)

### Security gate (SKBLD-06, 07, 08)

- **Trigger:** SecurityScanner runs **on Save**, before writing to DB. Applies to ALL saves — new builds, edits of existing active skills (re-scan on every edit), and forked skills.
- **On-save flow:**
  1. Admin clicks Save
  2. SecurityScanner runs synchronously on the draft content
  3. If recommendation = `approve` → skill saved as `active`
  4. If recommendation = `review` or `reject` → skill saved as `pending_review`; SecurityReportCard renders inline in the builder preview panel
- **SecurityReportCard placement (SKBLD-07):** After Save, the **right-side preview panel switches to SecurityReportCard view**: trust score (0–100), factor breakdown (progress bars per factor), tool permissions list, injection warning highlights, and recommendation badge (`approve` / `review` / `reject`).
- **Admin approval (SKBLD-08):** SecurityReportCard has an **"Approve & Activate" button** at the bottom for `review` or `reject` recommendations. Clicking shows a confirmation step ("I understand the security risks"). On confirm, skill transitions to `active`. No redirect needed — approval happens inline.
- **Re-scan on edit:** When admin edits an existing `active` skill in the builder and saves, the scan re-runs. If the re-scan now returns `review` or `reject`, the skill is moved back to `pending_review`. This ensures previously-approved skills don't accumulate silent regressions.
- **SecurityReportCard is a new A2UI component** (not an existing one) — displays in the builder preview panel, but can also be reused in the admin skill detail view.

### Claude's Discretion

- Exact pgvector index type for repo skill similarity (HNSW vs IVFFlat — HNSW preferred for small datasets)
- `handler_code` column name and exact status string for pending stubs (`pending_stub` or `draft`)
- SecurityReportCard visual design (factor bar colors, recommendation badge palette — follow existing badge patterns)
- Whether "Edit JSON" toggle shows a Monaco editor or a plain textarea
- Exact Claude Code field mapping for fields with no clean equivalent (e.g., `trigger`, `when_to_use`)
- Confirmation dialog copy for "Approve & Activate" override

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets

- `backend/agents/artifact_builder.py`: existing LangGraph builder agent — add new `generate_skill_content` node and `find_similar_skills` tool alongside existing `fill_form`. Extend `ArtifactBuilderState` with `similar_skills`, `security_report`, `handler_code` fields.
- `backend/agents/state/artifact_builder_types.py`: `ArtifactBuilderState` TypedDict — add: `similar_skills: list[dict] | None`, `security_report: dict | None`, `fork_source: str | None`.
- `backend/skills/security_scanner.py`: `SecurityScanner.scan()` — already enhanced with 6 factors (Phase 21). Drop-in for new security gate; no new factors needed. `ScanReport` dataclass already has `score`, `factors`, `recommendation`, `injection_matches`.
- `backend/skills/importer.py`: `SkillImporter.import_from_zip()` (done), `import_from_url()` (done) — add `import_from_claude_code_yaml()` method for Claude Code format adapter.
- `backend/core/models/skill_definition.py`: existing `source_type`, `status`, `procedure_json`, `instruction_markdown` columns — `source_type='imported'` + `status='pending_review'` is the established quarantine pattern.
- `backend/core/models/tool_definition.py`: add `handler_code TEXT` column (nullable) — migration 026 (Phase 22 migrations are 024-025).
- `backend/skill_repos/service.py`: existing `SkillRepoService` with cached index — add `search_similar(embedding: list[float], top_k: int) -> list[dict]` method using pgvector cosine search.
- `frontend/src/components/admin/artifact-builder-client.tsx`: builder frontend — extend right panel with: (1) Find Similar button + results list, (2) SecurityReportCard section post-save, (3) Edit JSON toggle.
- `frontend/src/components/admin/artifact-preview.tsx` (if exists) or builder preview — add SecurityReportCard render slot.
- `ArtifactCardGrid` (Phase 22): badge patterns established for "Featured" / "Shared" — SecurityReportCard recommendation badge follows same `Badge` component.

### Established Patterns

- `JSON().with_variant(JSONB(), 'postgresql')` on JSONB columns — `handler_code` is TEXT, no variant needed.
- `structlog.get_logger(__name__)` + `get_audit_logger()` for security gate decisions.
- `status='pending_review'` quarantine pattern: already used for imported skills. Builder-created skills that fail scan use the same status.
- `copilotkit_emit_state()` in builder nodes to push state updates to frontend in real-time — reuse for `similar_skills` and `security_report` fields.
- Migration chain: Phase 22 uses migrations up to ~025. Next migration for `handler_code` column is **026**.

### Integration Points

- `backend/api/routes/admin_skills.py`: existing `POST /import/zip` — no change. New: `POST /import/claude-code` for the Claude Code adapter endpoint (or handled in builder agent directly via tool call).
- `backend/api/routes/admin_tools.py`: add `PATCH /{tool_id}/activate-stub` to promote a `pending_stub` tool to active after admin fills the handler code.
- Builder agent → `SecurityScanner.scan()` call at the end of the save node.
- Frontend builder → new `SecurityReportCard` component rendered in preview panel when `state.security_report` is set.

</code_context>

<specifics>
## Specific Ideas

- The "Find Similar" button should appear only after the draft has at least a name and description — no empty-state search.
- Fork attribution note (`forked_from`) is primarily for the security audit trail, not for user-facing display.
- The "Edit JSON" toggle doesn't need to be a full Monaco editor — a `<textarea>` with JSON syntax highlighting is sufficient at this scale.
- For the Claude Code adapter, the `description:` field in Claude Code skill YAML is often a full paragraph — it should seed `instruction_markdown` directly, since Claude Code skills are inherently instructional.
- SecurityReportCard's "Approve & Activate" button should only be visible to users with `registry:manage` permission — same gate as the existing review workflow.
- ZIP import is already done — the builder's import panel "ZIP upload" tab just calls the existing endpoint. No backend work needed.

</specifics>

<deferred>
## Deferred Ideas

- **Batch re-scan of all existing skills** (admin-triggered "Re-scan all" button in /admin/skills) — useful operational tool but out of scope for Phase 23. Add to backlog.
- **Proactive similar skills** (auto-surface as user types) — deferred in favor of explicit "Find Similar" button. Could be a Phase 23.1 enhancement.
- **Skill composition** (one skill calling another) — explicitly listed as future requirement, deferred to v1.4+.
- **Auto-publish forked skills to agentskills.io** — out of scope (violates on-premise data requirement).

</deferred>

---

*Phase: 23-skill-platform-e-enhanced-builder*
*Context gathered: 2026-03-10*
