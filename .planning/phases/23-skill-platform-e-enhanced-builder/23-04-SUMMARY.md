---
phase: 23-skill-platform-e-enhanced-builder
plan: "04"
subsystem: skill-platform
tags:
  - security-gate
  - builder
  - frontend
  - react

dependency_graph:
  requires:
    - 23-01  # DB + type foundation (ArtifactBuilderState, SkillRepoIndex)
  provides:
    - POST /api/admin/skills/builder-save endpoint with SecurityScanner gate
    - SecurityReportCard component with trust score, factor bars, injection warnings
    - Builder-save wiring in artifact-builder-client (skills route to builder-save)
    - Inline Approve & Activate flow via existing review endpoint
  affects:
    - backend/api/routes/admin_skills.py
    - frontend/src/components/admin/artifact-builder-client.tsx

tech_stack:
  added:
    - BuilderSaveRequest/BuilderSaveResponse Pydantic models in admin_skills.py
    - SecurityReportCard React component (Tailwind, no new libraries)
  patterns:
    - TDD: failing tests first, then implementation
    - Route ordering: literal /builder-save declared before /{skill_id} catch-all
    - SecurityScanner called synchronously in FastAPI endpoint before DB write
    - State machine: approve→active, review/reject→pending_review, inline-approve→active
    - Conditional rendering: SecurityReportCard replaces ArtifactPreview on pending_review

key_files:
  created:
    - frontend/src/components/admin/security-report-card.tsx
    - backend/tests/skills/test_security_gate.py (rewritten from xfail stubs)
  modified:
    - backend/api/routes/admin_skills.py
    - frontend/src/components/admin/artifact-builder-client.tsx

decisions:
  - "[23-04]: BuilderSaveResponse returns skill_id + status + security_report — frontend uses status to decide whether to show SecurityReportCard or saveSuccess"
  - "[23-04]: SecurityReportCard uses pure Tailwind colored spans instead of shadcn Badge — no ui/badge.tsx exists in codebase"
  - "[23-04]: SecurityReportCard replaces ArtifactPreview (not overlays) on pending_review — cleaner UX, full panel for security info"
  - "[23-04]: Re-save of existing skill uses skill_id in BuilderSaveRequest body, updates existing row — avoids duplicate skills on re-scan"

metrics:
  duration: "~45 minutes (Tasks 1+2 + human-verify checkpoint)"
  completed_date: "2026-03-10"
  tasks_total: 3
  tasks_completed: 3
  files_created: 2
  files_modified: 2
---

# Phase 23 Plan 04: Builder Security Gate + SecurityReportCard Summary

**One-liner:** POST /api/admin/skills/builder-save endpoint gates every builder save through SecurityScanner, with SecurityReportCard showing trust score breakdown and inline Approve & Activate for flagged skills — human verified end-to-end.

## What Was Built

### Task 1: POST /api/admin/skills/builder-save (Backend)

Added `BuilderSaveRequest` and `BuilderSaveResponse` Pydantic models and a new `POST /api/admin/skills/builder-save` endpoint in `backend/api/routes/admin_skills.py`.

Key behaviors:
- Runs `SecurityScanner().scan(skill_data, source_url=...)` synchronously before any DB write
- `approve` recommendation → `status="active"`, `is_active=True` (skill immediately usable)
- `review` or `reject` → `status="pending_review"`, `is_active=False` (quarantined for review)
- Optional `skill_id` in request body → updates existing skill (re-scan on edit), avoids duplicate rows
- Route declared BEFORE `/{skill_id}` catch-all to prevent UUID routing conflict
- Audit log entry: `builder_save` event with score, recommendation, user_id
- Auth: `_require_registry_manager` (registry:manage permission required)

### Task 2: SecurityReportCard + Frontend Wiring

Created `frontend/src/components/admin/security-report-card.tsx`:
- Trust score display: large colored number (green=approve, yellow=review, red=reject)
- Recommendation badge: colored pill (no shadcn Badge — pure Tailwind, no badge.tsx exists)
- Factor breakdown: labeled progress bars for all 6 SecurityScanner factors
- Injection warnings: red-bordered box listing matched patterns (only shown when present)
- "Approve & Activate" button: only visible for review/reject; calls existing `/api/admin/skills/{id}/review` with `decision="approve"` after `window.confirm()` dialog; calls `onApproved()` on success

Modified `frontend/src/components/admin/artifact-builder-client.tsx`:
- Added `securityReport` and `savedSkillId` state variables
- `handleSave()` branches on `artifact_type === "skill"` → calls `builder-save` endpoint
- On `pending_review` response: sets `securityReport`, `savedSkillId`; does NOT set `saveSuccess`
- On `active` response: sets `saveSuccess` (existing flow unchanged)
- Right panel: conditionally renders `<SecurityReportCard>` instead of `<ArtifactPreview>` when `securityReport` is set and skill not yet active
- Non-skill artifact types (agents, tools, mcp_server) unchanged

## Verification Results

- `PYTHONPATH=. .venv/bin/pytest tests/skills/test_security_gate.py -q` → **3 passed** (no xfail)
- `pnpm exec tsc --noEmit` → **clean, no errors**
- Full backend suite: **844 passed** (3 pre-existing failures in 23-02/23-03 wave 2 stubs, unrelated)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Dependency] No shadcn Badge component in codebase**
- **Found during:** Task 2
- **Issue:** Plan referenced `from "@/components/ui/badge"` but `frontend/src/components/ui/` directory does not exist — no shadcn components installed in this project
- **Fix:** Implemented recommendation display with pure Tailwind CSS colored spans (`inline-flex` with `bg-green-100 text-green-800` etc.) matching project's existing pattern
- **Files modified:** `frontend/src/components/admin/security-report-card.tsx`

None other — plan executed as written for all other aspects.

## Human Verification: APPROVED

Task 3 checkpoint was approved by the user on 2026-03-10. Security gate flow verified end-to-end:
- Builder-save endpoint with SecurityScanner gate
- SecurityReportCard rendering in builder right panel
- Approve & Activate button with confirmation dialog and inline transition to active

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `frontend/src/components/admin/security-report-card.tsx` | FOUND |
| `backend/tests/skills/test_security_gate.py` | FOUND |
| Commit 7aea085 (builder-save endpoint) | FOUND |
| Commit ba6444c (SecurityReportCard + wiring) | FOUND |
| Human verification checkpoint | APPROVED |
