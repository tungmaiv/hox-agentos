---
phase: "24"
plan: "04"
subsystem: skill-import-adapters
tags: [skill-import, adapter-pattern, github-api, unified-registry, security-gate]
dependency_graph:
  requires: ["24-02"]
  provides: ["SkillAdapter ABC", "NormalizedSkill", "GitHubAdapter", "SkillRepoAdapter", "ClaudeMarketAdapter", "UnifiedImportService", "POST /api/registry/import"]
  affects: ["registry.py", "skills/adapters/", "skills/import_service.py"]
tech_stack:
  added: ["httpx (async HTTP in GitHubAdapter/SkillRepoAdapter)"]
  patterns: ["ABC adapter pattern", "conditional import guard for optional dependency"]
key_files:
  created:
    - backend/skills/adapters/__init__.py
    - backend/skills/adapters/base.py
    - backend/skills/adapters/skill_repo.py
    - backend/skills/adapters/github.py
    - backend/skills/adapters/claude_market.py
    - backend/skills/adapters/registry.py
    - backend/skills/import_service.py
    - backend/tests/skills/test_github_adapter.py
    - backend/tests/skills/test_import_service.py
  modified:
    - backend/api/routes/registry.py
    - backend/tests/test_skill_importer.py
decisions:
  - "[24-04]: can_handle() is synchronous (not async) in all adapters — URL pattern matching needs no I/O, synchronous check avoids event loop overhead in detect_adapter()"
  - "[24-04]: patch(..., create=True) required for scan_skill_with_fallback mock — attribute not present in module namespace when _HAS_SCANNER=False (ImportError guard)"
  - "[24-04]: SkillRepoAdapter.can_handle() returns False for github.com non-.md URLs — GitHubAdapter takes priority for repo browse, SkillRepoAdapter handles direct raw URLs"
  - "[24-04]: NotImplementedError from ClaudeMarketAdapter → HTTP 501 in import endpoint — correct semantics (feature not implemented, not client error)"
metrics:
  duration: "8 minutes"
  completed: "2026-03-12T03:16:50Z"
  tasks_completed: 2
  files_changed: 10
requirements_satisfied:
  - 24-04-SKL
---

# Phase 24 Plan 04: Pluggable Skill Import Adapter Framework Summary

**One-liner:** Pluggable SkillAdapter ABC + NormalizedSkill dataclass + 3 concrete adapters (SkillRepo, GitHub, ClaudeMarket stub) + UnifiedImportService with security gate + POST /api/registry/import endpoint.

## What Was Built

### adapter framework (`backend/skills/adapters/`)

- **base.py** — `NormalizedSkill` dataclass (canonical import output) + `SkillAdapter` ABC with 4 abstract methods: `can_handle()` (sync), `validate_source()`, `fetch_and_normalize()`, `get_skill_list()`.
- **skill_repo.py** — `SkillRepoAdapter`: wraps existing `SkillImporter.import_from_url()` without rewriting. Handles `http/https://` URLs (except GitHub repo browse). Maps importer's dict output to `NormalizedSkill`.
- **github.py** — `GitHubAdapter`: uses GitHub Trees API (`/repos/{owner}/{repo}/git/trees/HEAD?recursive=1`) to discover skill files. Filters for `SKILL.md`, `skill.yaml`, `skill.yml`. Fetches via `raw.githubusercontent.com`. Reuses `SkillImporter.parse_skill_md()` and `import_from_claude_code_yaml()`.
- **claude_market.py** — `ClaudeMarketAdapter` MVP stub: `can_handle()` returns True for `claude-market://` prefix; `fetch_and_normalize()` and `get_skill_list()` raise `NotImplementedError`.
- **registry.py** — `AdapterRegistry.detect_adapter()`: priority order ClaudeMarket → GitHub → SkillRepo → `ValueError`.

### import service (`backend/skills/import_service.py`)

`UnifiedImportService.import_skill()` pipeline:
1. `AdapterRegistry.detect_adapter(source)` → select adapter
2. `adapter.validate_source(source)` → reachability check
3. `adapter.fetch_and_normalize(source)` → `NormalizedSkill`
4. `scan_skill_with_fallback()` (if `_HAS_SCANNER=True`) → security scan
5. `UnifiedRegistryService.create_entry()` → `RegistryEntry` with `type="skill"`

`_HAS_SCANNER` flag: `try/except ImportError` on `security.scan_client` import. False until plan 24-05 creates that module. Tests use `patch(..., create=True)` to mock the attribute regardless.

### API endpoint (`backend/api/routes/registry.py`)

`POST /api/registry/import` (201):
- `ImportSkillRequest` — `source: str`, `source_type: str | None`
- `ImportSkillResponse` — `id`, `name`, `status`, `security_score`
- Requires `registry:manage` permission (it-admin)
- `ValueError` → 422, `NotImplementedError` → 501

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `patch()` AttributeError for `scan_skill_with_fallback` when `_HAS_SCANNER=False`**
- **Found during:** Task 2 test execution
- **Issue:** When `_HAS_SCANNER=False` (ImportError guard), `scan_skill_with_fallback` is not in the module's `__dict__`. `patch("skills.import_service.scan_skill_with_fallback")` raises `AttributeError: module has no attribute 'scan_skill_with_fallback'`.
- **Fix:** Added `create=True` parameter to all `@patch(...)` decorators in `test_import_service.py`. This tells `unittest.mock` to create the attribute even if it doesn't exist yet.
- **Files modified:** `backend/tests/skills/test_import_service.py`

## Tests Added

| Test File | Count | Coverage |
|-----------|-------|----------|
| `tests/skills/test_github_adapter.py` | 4 | GitHubAdapter can_handle, get_skill_list, fetch_and_normalize |
| `tests/test_skill_importer.py` (added) | 2 | SkillRepoAdapter can_handle + fetch_and_normalize |
| `tests/skills/test_import_service.py` | 5 | UnifiedImportService routing, registry entry, scan gate, no-scan fallback, unknown source |
| **Total new** | **11** | |

**Full suite:** 882 passed, 7 skipped (up from pre-phase baseline).

## Self-Check: PASSED

Files verified:
- `backend/skills/adapters/__init__.py` — FOUND
- `backend/skills/adapters/base.py` — FOUND
- `backend/skills/adapters/registry.py` — FOUND
- `backend/skills/adapters/skill_repo.py` — FOUND
- `backend/skills/adapters/claude_market.py` — FOUND
- `backend/skills/adapters/github.py` — FOUND
- `backend/skills/import_service.py` — FOUND
- `backend/api/routes/registry.py` — POST /import endpoint confirmed present

Commits verified:
- `e7e3ba0` — feat(24-04): adapters
- `b9fdbc8` — feat(24-04): import service + endpoint
