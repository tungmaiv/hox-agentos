---
created: 2026-03-15T06:51:58.504Z
title: "Implement Universal Skill Import (Topic #05)"
area: general
priority: medium
target: v1.5-enhancement
effort: 4-5 weeks
existing_code: 40%
depends_on: []
design_doc: docs/enhancement/topics/05-universal-skill-import/00-specification.md
files:
  - backend/skills/adapters/base.py
  - backend/skills/adapters/github.py
  - backend/skills/adapters/skill_repo.py
  - backend/skills/adapters/claude_market.py
  - backend/skills/adapters/registry.py
  - backend/skills/import_service.py
  - backend/skills/importer.py
  - backend/security/scan_client.py
  - frontend/src/app/(authenticated)/admin/skill-store/page.tsx
---

## Problem

The skill import pipeline exists with adapter pattern, GitHub adapter, security scanning, and skill store UI. However, the spec calls for significant extensions: tool bundling with sandbox enforcement, an import approval queue, and new database tables. The existing code handles the "import skills from URLs" use case well but lacks the "skills that carry their own private tools" architecture.

## What Exists (40%)

- `SkillAdapter` ABC with 4 methods (can_handle, validate_source, fetch_and_normalize, get_skill_list)
- `GitHubAdapter` — fetches from public GitHub repos (Trees API, SKILL.md + YAML parsing) ✅ ALREADY EXISTS
- `SkillRepoAdapter` — direct URL fetch
- `ClaudeMarketAdapter` — claude-market:// protocol
- `AdapterRegistry` — auto-detection of source type
- `UnifiedImportService` — full pipeline: detect → validate → fetch → scan → create
- `SecurityScanClient` — Docker scanner + in-process fallback (Bandit + pip-audit)
- `SkillImporter` — SKILL.md frontmatter parsing, ZIP bundle import, MANIFEST.json fallback, Claude Code YAML
- Skill Store UI — browse tab + repositories tab
- `SkillRepository` model — remote repo metadata, cached index

## What's Needed (60% new work)

- **3 new database tables:**
  - `skill_references` — external references attached to skills (docs, API refs, examples)
  - `skill_output_formats` — output format specifications (JSON schema, templates)
  - `skill_import_queue` — approval queue for skills pending admin review
- **Tool bundling system:**
  - `ToolBundle` dataclass, `ToolVisibility` enum (public/private/protected)
  - `RawSkillBundle` structure with `tools/`, `references/`, `schemas/` directories
  - Private tools must enforce sandbox execution (no exceptions)
- **ToolDefinition schema changes:**
  - New columns: `visibility`, `parent_skill_id`, `sandbox_required`, `bundled_from_source`, `bundled_from_version`
- **Import approval workflow:**
  - `ImportDecisionEngine` service — immediate vs approval routing
  - Admin approve/reject flow
  - Import queue UI in admin console
- **Multi-skill repo structure** — `skills/` folder support in GitHub adapter
- **Private repo auth** — PAT token handling for private GitHub repos
- **Observability** — Prometheus counters for imports, sandbox executions, tool usage

## Solution

Follow specification at `docs/enhancement/topics/05-universal-skill-import/00-specification.md`.
