---
status: complete
phase: 23-skill-platform-e-enhanced-builder
source: [23-01-SUMMARY.md, 23-02-SUMMARY.md, 23-03-SUMMARY.md, 23-04-SUMMARY.md]
started: 2026-03-10T00:00:00Z
updated: 2026-03-11T00:00:00Z
---

## Tests

### 1. Generate instructional skill content in builder
expected: Open the artifact builder and select "Skill" type. Enter an instructional goal (e.g., "project plan skill — ask questions, propose plan, allow modifications, produce markdown file"). The AI should generate instruction_markdown content AND populate the Instructions field in the form.
result: FAIL (fixed b8a821c) — fill_form tool had no instruction_markdown param; silently dropped. Fix: added param to fill_form signature, _fill_form_node, _FILL_FORM_ARG_TO_STATE, ArtifactBuilderState, and frontend useEffect mapping.

### 1+2. Generate skill content in builder (instructional)
expected: Describe a skill goal. AI generates name, description, and instruction_markdown all populated in the form fields.
result: PASS (after fixes b8a821c, 64735e4, 7aa25f8, 5b564bd)

### 3. Generate tool handler stub
expected: Select "Tool" type in the artifact builder, provide a name and description. AI generates Python stub with InputModel/OutputModel + async handler(). Stub saved as pending_stub in DB.
result: PARTIAL PASS — Python stub generated with InputModel/OutputModel ✓, appeared in chat ✓, tool saved ✓. But handler_code not persisted and tool saved as active instead of pending_stub. Fixed in b40c365: added handler_code to ToolDefinitionCreate, set pending_stub status when stub present, captured handler_code from coagent state in wizard.

### 4. Import Claude Code skill from GitHub URL
expected: In the builder's import panel (if accessible via UI), paste a GitHub blob URL to a Claude Code skill YAML file (e.g., a github.com/.../blob/... path). The system fetches and parses it, converting to a skill draft with name, description, and instruction_markdown pre-populated from the YAML fields. The draft appears ready for AI-assisted adaptation.
result: SKIPPED — No import panel UI exists in Builder+ or Skills page. Backend endpoint POST /api/admin/skills/import is implemented but not wired to any frontend. Deferred.

### 5. Edit JSON toggle on a draft
expected: After a skill draft has been generated (any type), an "Edit JSON" toggle appears below the preview panel. Clicking it shows a textarea pre-filled with the current draft as formatted JSON. Editing the JSON and clicking "Parse" applies the changes to the draft. Invalid JSON shows an inline parse error without crashing.
result: PASS (after fixes 61f4083, 2301aef, 0fac314, f24130b) — gather_type→validate_and_present routing fixed; is_complete now set correctly; prompt updated to kebab-case; 1-arg JSON blobs captured; manualDraftRef prevents co-agent polling from overwriting user edits.

### 6. Find Similar button appears and searches
expected: In the artifact builder, after entering both a name and description for a draft (but before generating content), a "Find Similar" button appears in the right panel. Clicking it searches external skill repos and shows up to 5 similar skill cards, each with the skill name, description snippet, and repository name. If no matches, shows "No similar skills found".
result: PASS — Find Similar button visible after draft complete; search ran and returned "No similar skills found" (no repos indexed — correct behavior).

### 7. Fork an external skill into draft
expected: From the similar skills results, clicking "Fork" on any result copies that skill's name and description into the current draft fields and collapses the results panel. A fork attribution badge or note appears showing the source skill name and URL. The draft is now pre-populated and ready for builder AI refinement.
result: SKIPPED — No skill repos indexed, so no Fork buttons to click. Backend fork logic exists in artifact-builder-client.tsx (handleFork). Deferred until repos are synced.

### 8. Builder Save triggers Security Gate (approved path)
expected: After generating a skill draft in the builder, click Save. The endpoint runs the SecurityScanner. If the skill looks clean (simple instructional skill with no tool permissions or suspicious patterns), the skill is saved as "active" immediately and the builder shows a success state. No SecurityReportCard shown for clean skills.
result: PASS — email-summary saved as active (Score: 85), no SecurityReportCard shown.

### 9. SecurityReportCard shown for flagged saves
expected: Save a skill that would trigger a security review (e.g., one with tool access to email and calendar, or one with content that looks like prompt injection). The right panel switches from the preview to a SecurityReportCard showing: a trust score (0–100), factor breakdown bars (one per security factor), injection warning text if present, and a recommendation badge (review or reject).
result: PASS (after fix f24130b) — SecurityReportCard shown with score 75/100, "Needs Review" badge, factor breakdown bars, Injection Pattern Warnings section. Root cause of initial failure: co-agent polling overwrote user's JSON edits 100ms after Parse. Fixed with manualDraftRef lock.

### 10. Approve & Activate flagged skill inline
expected: When SecurityReportCard is shown for a pending_review skill, an "Approve & Activate" button appears at the bottom. Clicking it shows a confirmation dialog. Confirming transitions the skill to "active" status inline — no page redirect. The builder reflects the approval (e.g., returns to success state or shows the skill as active).
result: PASS — "Approve & Activate" button visible on SecurityReportCard for "review" recommendation; confirmation dialog shown; confirming activates inline.

## Summary

total: 10
passed: 7
issues: 0
pending: 0
skipped: 3

## Gaps

1. **Import UI missing** (Test 4) — Backend POST /api/admin/skills/import exists but no frontend panel in Builder+ or Skills page. Need to add an import URL input to the Builder+ right panel.

2. **Fork untested** (Test 7) — handleFork() implemented but untestable without indexed skill repos. Needs at least one synced repo to verify end-to-end.

3. **Security scanner is code-only** — Hybrid AI + code scoring requested. Plan: code scanner runs first (fast pre-screen), LLM reviewer runs second only when score < 80 for deeper analysis. Implement as quick task.

4. **Reject = hard block not enforced** — "Approve & Activate" currently shows for both "review" and "reject". Design decision: reject should be a hard block (no inline activation). Fix: change `recommendation !== "approve"` → `recommendation === "review"` in SecurityReportCard.

5. **LLM output inconsistency** — gather_type_node sometimes outputs null-filled schema templates. Prompt fix (a41d4b0) reduces frequency but LLM non-determinism means it can still occur. A code-level null filter in _extract_draft_from_response would be a reliable fallback.
