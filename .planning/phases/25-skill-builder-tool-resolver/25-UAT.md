---
status: diagnosed
phase: 25-skill-builder-tool-resolver
source: [25-01-SUMMARY.md, 25-02-SUMMARY.md, 25-03-SUMMARY.md, 25-04-SUMMARY.md, 25-05-SUMMARY.md]
started: 2026-03-14T00:00:00Z
updated: 2026-03-14T01:00:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

[testing complete]

## Tests

### 1. Bell dropdown opens on click
expected: Go to any admin page (e.g. /admin/skills). Look at the top nav/header — there is a bell icon. Click it. A dropdown opens. If there are no pending skills, it shows "No skills pending activation" (not nothing, not blank, not an error).
result: pass

### 2. Artifact builder saves a new skill
expected: Go to /admin/agents and open the Artifact Builder. Complete the wizard to create a simple instructional skill (any name/description). Click Save. The save succeeds without an error. The new skill appears in the /admin/skills list.
result: pass

### 3. Draft badge on newly saved skill
expected: After saving a skill via the artifact builder (test 2), go to /admin/skills. The new skill has a grey "draft" badge in the Status column — visually distinct from green "active" and amber "pending_activation".
result: issue
reported: "newly saved skill slack-summary shows active (green) badge, not draft (grey)"
severity: major

### 4. Pending activation amber badge
expected: In /admin/skills, a skill that has been auto-promoted to "pending_activation" (all its tool gaps resolved) shows an amber/orange badge in the Status column — visually distinct from grey draft and green active.
result: skipped
reason: No pending_activation skills exist — cascade from test 3 (builder saves as active not draft, so gap/promotion flow never triggers)

### 5. Draft skill gap tooltip
expected: In /admin/skills, a draft skill that has unresolved tool gaps shows a ⚠️ warning icon next to its status badge. Hovering over the icon reveals a tooltip like "X unresolved tool gap(s)".
result: skipped
reason: No draft skills with tool_gaps exist — cascade from test 3

### 6. Inline Activate button for pending_activation skills
expected: In /admin/skills, a skill with "pending_activation" status has a blue "Activate" button directly in its table row (not in a dropdown, not behind a modal). Clicking it calls the backend and the skill switches to "active" with a green badge.
result: skipped
reason: No pending_activation skills exist — cascade from test 3

### 7. Draft lock — cannot activate skill with tool gaps
expected: In /admin/skills, a draft skill that has unresolved tool_gaps does NOT have a blue "Activate" button (or if it does, clicking it shows an error). The skill cannot be switched to active while gaps exist.
result: skipped
reason: No draft skills with tool_gaps exist — cascade from test 3

### 8. Bell icon shows live count for pending skills
expected: When one or more skills are in "pending_activation" status, the bell icon in the admin nav shows an orange badge with the count (e.g. "1" or "2"). When none are pending, the badge is absent or shows 0.
result: pass

### 9. Bell dropdown lists pending skills
expected: When pending_activation skills exist, clicking the bell icon opens a dropdown listing the names of those skills, each linking to /admin/skills.
result: pass

### 10. Artifact wizard sends correct skill_type
expected: When building a procedural skill in the artifact builder (selecting "procedural" as skill type), the saved skill shows up in /admin/skills as a procedural skill (not instructional). The skill_type field in the backend reflects what the user selected.
result: pass

## Summary

total: 10
passed: 5
issues: 1
pending: 0
skipped: 4

## Gaps

- truth: "A skill saved via the artifact builder starts in draft status"
  status: failed
  reason: "User reported: newly saved skill slack-summary shows active (green) badge, not draft (grey)"
  severity: major
  test: 3
  root_cause: "POST /api/admin/skills (create_skill) passes status='active' to RegistryEntryCreate (admin_skills.py line 234). SkillHandler.on_create() only downgrades to draft when tool_gaps is non-empty — it never touches status for gap-free skills. The artifact wizard calls POST /api/admin/skills, not builder-save."
  artifacts:
    - path: "backend/api/routes/admin_skills.py"
      issue: "Line 234: status='active' should be status='draft'"
  missing:
    - "Change status='active' to status='draft' in create_skill endpoint (admin_skills.py line 234)"
    - "Add test to test_admin_skills.py asserting POST /api/admin/skills returns status='draft'"
  debug_session: "ad4cc3c45381eeae6"
