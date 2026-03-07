# Phase 19 Plan 01: Skill Platform A — Standards Compliance Summary

## One-liner
Implemented full agentskills.io spec compliance: 7 metadata columns, kebab-case name validation, SKILL.md import/export with frontmatter, ZIP bundle import/export, and admin UI metadata panel.

## What Was Built

### 19-01: Migration 022 + ORM + Schema + Name Validation
- Migration `022_skill_standards_columns.py`: adds 7 columns to `skill_definitions` — `license`, `compatibility`, `metadata_json`, `allowed_tools`, `tags`, `category`, `source_url`
- ORM model: 7 new `Mapped` columns (Text / JSONB variants)
- Pydantic schemas: `SkillCreate`, `SkillUpdate`, `SkillResponse` all include the 7 new fields
- Name validator on `SkillCreate`: kebab-case, 1–64 chars, no consecutive hyphens — raises 422 on violation
- 74 test updates to use kebab-case skill names throughout the test suite

### 19-02: SKILL.md Importer — Frontmatter + ZIP Bundle
- `skills/importer.py`: parses 7 new agentskills.io frontmatter fields from SKILL.md (`license`, `compatibility`, `allowed-tools`, `tags`, `category`, `metadata` dict, `source_url`)
- `import_from_zip()`: validates ZIP structure, finds SKILL.md (root or top-level dir), merges `MANIFEST.json` as fallback for missing fields, rejects corrupt ZIPs and missing SKILL.md with 422 + clear messages
- Added `python-multipart` dependency for file upload support
- 25 importer tests (15 new)

### 19-03: Skill Export — MANIFEST.json + assets/ + Frontmatter Fields
- `skill_export/exporter.py`: `build_skill_zip()` now includes `MANIFEST.json` (full metadata mirror with `schema_version: "1.0"`) and `assets/` directory
- `_build_skill_md()`: emits 7 new fields in SKILL.md frontmatter when non-null
- `_build_manifest()`: serializes all 7 fields + skill_type, slash_command, source_type, security_score
- 27 export tests (9 new)

### 19-04: ZIP Import Route
- `POST /api/admin/skills/import/zip`: multipart file upload, delegates to `import_from_zip()`, runs security scan, stores as `pending_review`
- Route declared before `/{skill_id}` to avoid UUID match collision

### 19-05: Admin UI Metadata Panel
- `SkillDefinition` TypeScript interface: +7 optional fields
- `SkillMetadataPanel` component in `admin/skills/page.tsx`: renders non-null fields with labels, `allowed_tools` as blue mono chips, `tags` as gray chips
- Panel renders in card grid view's `renderExtra` slot

### Post-UAT Fixes (same session)
- **Migration 022 not in container**: copied `83f730920f5a` and `022` migration files into running container, ran `alembic upgrade head`
- **`[object Object]` error display**: `use-admin-artifacts.ts` `create()` now extracts `.msg` from first Pydantic validation error item instead of casting array to string
- **`source_url` not parsed from frontmatter**: added `if "source_url" in frontmatter: skill_data["source_url"] = frontmatter["source_url"]` in `importer.py` + regression test
- **Next.js proxy corrupts binary multipart**: `api/admin/[...path]/route.ts` now uses `request.arrayBuffer()` for `multipart/form-data` requests instead of `request.text()`

## Test Results
- Backend: 794 tests passing (up from 719 pre-phase), 1 skipped
- Frontend: TypeScript strict check clean (`pnpm exec tsc --noEmit` exit 0)
- UAT: 5/5 tests pass (see `19-UAT.md`)

## Files Changed
- `backend/alembic/versions/022_skill_standards_columns.py` (new)
- `backend/api/routes/admin_skills.py`
- `backend/core/models/skill_definition.py`
- `backend/core/schemas/registry.py`
- `backend/skill_export/exporter.py`
- `backend/skills/importer.py`
- `backend/pyproject.toml` (python-multipart)
- `backend/tests/test_skill_importer.py` (+regression test)
- `backend/tests/test_skill_export.py`
- `frontend/src/app/(authenticated)/admin/skills/page.tsx`
- `frontend/src/lib/admin-types.ts`
- `frontend/src/hooks/use-admin-artifacts.ts`
- `frontend/src/app/api/admin/[...path]/route.ts`
