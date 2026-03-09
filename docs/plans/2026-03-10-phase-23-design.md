# Phase 23: Skill Platform E — Enhanced Builder

**Date:** 2026-03-10
**Approach:** C (two plans, drop SKBLD-03 tool scaffolding)
**Requirements:** SKBLD-01, SKBLD-02, SKBLD-04, SKBLD-05, SKBLD-06, SKBLD-07, SKBLD-08
**Dropped:** SKBLD-03 (Python tool scaffolding — deferred to future phase)

---

## Architecture Overview

Two plans with clean separation. No new DB tables, no new services. Both plans use existing infrastructure.

- **Plan 23-01** — Security gate on all artifacts
- **Plan 23-02** — Similar skills search + fork + builder quality

---

## Plan 23-01: Security Gate on All Artifacts

### Problem

User-created skills from the artifact builder are saved directly as `status="active"` without going through `SecurityScanner`. Imported skills get scanned; builder skills don't. This is a security gap.

### Backend

1. **New endpoint** `POST /api/admin/skills/scan-preview`
   - Accepts a skill definition dict (not yet saved)
   - Runs `SecurityScanner.scan()` and returns the report
   - Called by the wizard UI before saving

2. **Builder save flow change** (`POST /api/admin/skills`)
   - Always run `SecurityScanner` on `source_type="user_created"` skills at save time
   - score ≥ 80 → `status="active"` (unchanged)
   - score < 60 or 60–79 → `status="pending_review"` (currently these go to active)
   - Store `security_score` and `security_report` on the record (columns already exist)

3. No schema changes — `security_score`, `security_report`, approve/reject endpoints all exist.

### Frontend

1. **`SecurityReportCard` component** — shown in artifact wizard after `[DRAFT_COMPLETE]`
   - Trust score 0–100 with color coding: green (≥80), amber (60–79), red (<60)
   - Factor breakdown table: source_reputation, tool_scope, prompt_safety, complexity, dependency_risk, data_flow_risk
   - Injection warnings list (if any)
   - Recommendation badge: `approve` / `review` / `reject`

2. **Wizard flow change**
   - After `[DRAFT_COMPLETE]` detected: call `scan-preview` → show `SecurityReportCard` → show Save button
   - If recommendation is `review` or `reject`: Save button shows warning "This skill will go to the admin review queue before activation"
   - If `approve`: Save button is green, skill activates immediately on save

3. **Admin review queue** — no changes needed; `pending_review` skills already surface at `/admin/skills` with existing approve/reject actions.

### Flow

```
Builder chat → [DRAFT_COMPLETE]
  → POST /api/admin/skills/scan-preview
  → SecurityReportCard rendered in wizard
  → Admin clicks Save
      → score ≥ 80: saved as active
      → score < 80: saved as pending_review → admin approves in review queue
```

---

## Plan 23-02: Similar Skills + Fork + Builder Quality

### Backend

1. **New endpoint** `GET /api/admin/skills/similar?q=<text>&limit=5`
   - Searches `cached_index_json` on existing `SkillRepository` records (built in Phase 20)
   - Keyword match against skill names and descriptions
   - Returns top 3–5 matches with full skill definition

2. **New endpoint** `POST /api/admin/skills/fork`
   - Accepts an external skill definition (from repo index)
   - Runs `SecurityScanner` on it
   - Saves with `source_type="imported"`, `status="pending_review"`
   - Returns new skill ID
   - Reuses existing import path — no new logic

3. **Builder prompt improvement** (`backend/prompts/artifact_builder_skill.md`)
   - Add complete `procedure_json` examples with conditions, prompt templates, realistic tool references
   - Current prompt only shows instructional examples; procedural guidance is thin

### Frontend

1. **Similar Skills panel** in artifact wizard
   - Appears once user has typed a name/description (debounced, ~500ms)
   - Shows top 3–5 external skill cards: name, description, source repo, trust score
   - Two actions per card: "Fork this" and "Use as reference"

2. **"Fork this"** — calls `POST /api/admin/skills/fork`
   - Redirects to skill edit page with forked skill pre-populated
   - Fork goes through security gate automatically at save (Plan 23-01 already in place)

3. **"Use as reference"** — lighter option
   - Copies skill's `instruction_markdown` or `procedure_json` into builder chat as context
   - No new DB record created
   - Builder LLM uses it to guide the new skill's structure

### Flow

```
Admin opens builder → types description
  → similar panel: top 3–5 matches appear

  Path A — Fork:
    "Fork this" → POST /api/admin/skills/fork → saved pending_review
    → admin approves in review queue → active

  Path B — Reference:
    "Use as reference" → injected into chat context
    → builder continues → [DRAFT_COMPLETE] → security gate (Plan 23-01) → save

  Path C — Build from scratch:
    builder chat → [DRAFT_COMPLETE] → security gate → save
```

---

## Constraints

- No new DB tables
- No new Docker services
- Fork reuses existing import path
- Similar search reads `cached_index_json` already in `SkillRepository`
- Security gate in Plan 23-01 is the prerequisite for Plan 23-02 (fork must go through gate)
