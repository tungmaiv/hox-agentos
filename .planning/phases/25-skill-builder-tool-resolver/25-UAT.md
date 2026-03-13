---
status: resolved
phase: 25-skill-builder-tool-resolver
source: [25-01-SUMMARY.md, 25-02-SUMMARY.md, 25-03-SUMMARY.md, 25-04-SUMMARY.md, 25-05-SUMMARY.md]
started: 2026-03-13T00:00:00Z
updated: 2026-03-13T12:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Pending activation amber badge in admin skills table
expected: Go to /admin/skills. Any skill with status "pending_activation" shows an amber/orange badge (not yellow, not green). Draft skills show a grey badge. The badge colors are visually distinct from each other and from active (green).
result: skipped
reason: No pending_activation skills exist in current data. Draft=grey and active=green confirmed visible. Cannot verify amber without a pending_activation skill (blocked by test 7 being a blocker).

### 2. Draft skill gap tooltip
expected: A draft skill that has unresolved tool gaps shows a ⚠️ warning icon in the status column. Hovering over it reveals a tooltip saying something like "X unresolved tool gap(s)".
result: skipped
reason: Existing draft skills predate phase 25 and have no tool_gaps. Cannot create a new one (test 7 blocker).

### 3. Inline Activate button for pending_activation skills
expected: In the admin skills table, a skill with "pending_activation" status has a blue inline "Activate" button in its row. Clicking it calls the backend and switches the skill to active.
result: skipped
reason: Cannot test — depends on a pending_activation skill existing, which requires skill creation (test 7) to work first.

### 4. Bell icon in admin nav with live count
expected: The admin nav header shows a bell icon. When there are pending_activation skills, an orange badge on the bell shows the count (e.g., "2"). When there are none, the badge is absent or shows 0.
result: pass

### 5. Bell dropdown lists pending skills
expected: Clicking the bell icon opens a dropdown listing the names of pending_activation skills, each linking to /admin/skills.
result: issue
reported: "I click to the bell but nothing happened"
severity: minor

### 6. Draft lock — cannot activate a skill with tool gaps
expected: A skill in draft status that has unresolved tool_gaps cannot be activated via the registry. Attempting to set it to active results in a 422 error. The skill stays in draft.
result: skipped
reason: Cannot test — depends on a draft skill with tool_gaps existing, which requires skill creation (test 7) to work first.

### 7. Auto-promotion when tool registered (+ skill creation)
expected: When a new tool is created that matches the intent of a skill's tool gap, the draft skill is automatically promoted to "pending_activation". The tool creation API response includes an "unblocked_skills" field.
result: issue
reported: "I cant save the skill 500 error"
severity: blocker

## Summary

total: 7
passed: 1
issues: 3
pending: 0
skipped: 4

## Gaps

- truth: "Clicking the bell icon in admin nav opens a dropdown listing pending_activation skills"
  status: resolved
  reason: "Fixed in plan 25-05 — bell dropdown now renders whenever bellOpen is true (not gated on pendingCount > 0). Empty-state message shown when no pending skills."
  severity: minor
  test: 5

- truth: "Artifact builder saves new skills via registry_entries (unified registry from phase 24)"
  status: resolved
  reason: "Fixed in plan 25-04 — builder_save migrated from SkillDefinition ORM (dropped table) to UnifiedRegistryService.create_entry() / update_entry(). 929 tests passing."
  severity: blocker
  test: 7

- truth: "Artifact wizard sends the correct skill_type (instructional vs procedural) selected by the user"
  status: resolved
  reason: "Fixed in plan 25-05 — artifact-wizard now uses formState.skill_type instead of hardcoded 'instructional'. procedure_json sourced from aiArtifactDraft for procedural skills."
  severity: major
  test: 7-additional
