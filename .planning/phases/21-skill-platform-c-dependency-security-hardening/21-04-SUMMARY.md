---
phase: 21-skill-platform-c-dependency-security-hardening
plan: "04"
subsystem: skill-security
tags: [skill-platform, security, importer, dependency-scanning, tdd]
dependency_graph:
  requires: [21-01]
  provides: [declared_dependencies, scripts_content in skill_data]
  affects: [SecurityScanner._score_dependency_risk, admin skill import flow]
tech_stack:
  added: []
  patterns: [TDD red-green, ZIP AST extraction, requirements.txt parsing, hard veto in scorer]
key_files:
  created: []
  modified:
    - backend/skills/importer.py
    - backend/skills/security_scanner.py
    - backend/tests/test_skill_importer.py
decisions:
  - "[21-04]: SecurityScanner hard veto: dependency_risk==0 with scripts_content forces reject regardless of weighted sum — weighted scoring alone cannot enforce undeclared-import rejection"
  - "[21-04]: Frontmatter dependencies: takes priority over scripts/requirements.txt — SKILL.md is the authoritative declaration"
  - "[21-04]: requirements.txt version specifiers stripped via re.split on =<>!~; — package name extracted cleanly"
metrics:
  duration: ~8 minutes
  completed: "2026-03-08"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 3
---

# Phase 21 Plan 04: SkillImporter Dependency and Scripts Extraction Summary

**One-liner:** Extended SkillImporter to extract declared_dependencies (frontmatter or requirements.txt) and scripts_content (ZIP scripts/ .py files), plus SecurityScanner hard veto for undeclared third-party imports.

## What Was Built

### `backend/skills/importer.py` changes

**`parse_skill_md()` extension:**
- Parses `dependencies:` frontmatter field into `skill_data["declared_dependencies"]`
- Supports both YAML list (`[requests, httpx]`) and space-delimited string (`"requests httpx"`)
- Only populated when `dependencies:` key is present — absent key leaves field absent

**`import_from_zip()` extension:**
- Extracts all `scripts/*.py` files from ZIP into `skill_data["scripts_content"]` as `list[{"filename": str, "source": str}]`
- Reads `scripts/requirements.txt` as fallback when no frontmatter `declared_dependencies` — strips version specifiers (`requests==2.31.0` → `requests`)
- Frontmatter dependencies take priority over requirements.txt (only reads requirements.txt if `"declared_dependencies" not in skill_data`)

### `backend/skills/security_scanner.py` auto-fix (Rule 1 — Bug)

**Hard veto added to `scan()`:**
- When `dependency_risk == 0` (undeclared third-party imports found) AND `scripts_content` is non-empty → force `recommendation = "reject"` regardless of weighted score
- Previous behavior: weighted sum (0.20 weight on dependency_risk) could not overcome other factors — a clean skill with an undeclared import would score ~65 ("review") instead of "reject"
- This aligns scanner behavior with its documented intent ("undeclared imports → immediate rejection")

### `backend/tests/test_skill_importer.py` additions

**`TestDependencyParsing` class (5 tests):**
- `test_dependencies_list_parsed` — YAML list → declared_dependencies list
- `test_dependencies_string_parsed` — space-delimited string → declared_dependencies list
- `test_no_dependencies_field` — absent key → field absent
- `test_dependencies_from_requirements_txt_in_zip` — requirements.txt fallback with version specifiers
- `test_frontmatter_deps_take_priority_over_requirements_txt` — frontmatter wins over requirements.txt

**`TestZipScripts` class (4 tests):**
- `test_scripts_py_extracted` — scripts/helper.py extracted with filename and source
- `test_no_scripts_directory_empty_list` — absent scripts/ → empty/absent scripts_content
- `test_non_py_files_in_scripts_ignored` — .txt files in scripts/ not included
- `test_undeclared_import_triggers_rejection` — integration: paramiko undeclared → SecurityScanner rejects

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend importer — dependencies frontmatter, scripts/ extraction, requirements.txt fallback | fdfeef1 | importer.py, security_scanner.py, test_skill_importer.py |

## Test Results

- New tests: 9 added (TestDependencyParsing: 5, TestZipScripts: 4) — all pass
- Security scanner tests: 34 — all pass (no regressions from hard veto change)
- Full suite: 825 passed, 1 skipped (baseline was 719 at v1.2 ship)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SecurityScanner hard veto for undeclared imports**
- **Found during:** Task 1 — integration test `test_undeclared_import_triggers_rejection` was returning "review" instead of "reject"
- **Issue:** Weighted scoring (dependency_risk has 0.20 weight) gives score of 65 for a skill with clean source/tools but undeclared imports. Score 65 maps to "review" (threshold 60-79), not "reject". The scanner's comment said "immediate rejection" but the code did not enforce it.
- **Fix:** Added hard veto check in `SecurityScanner.scan()`: if `dependency_risk == 0` AND `scripts_content` is non-empty, force `recommendation = "reject"` before weighted score threshold check.
- **Files modified:** `backend/skills/security_scanner.py`
- **Commit:** fdfeef1

## Self-Check

### Files created/modified

- `backend/skills/importer.py` — modified (SKSEC-01 dependency and scripts extraction)
- `backend/skills/security_scanner.py` — modified (hard veto for undeclared imports)
- `backend/tests/test_skill_importer.py` — modified (TestDependencyParsing + TestZipScripts)

### Verification commands from plan

```
grep -n "declared_dependencies\|scripts_content" backend/skills/importer.py
```
Result: Lines 153, 157, 237, 243, 246, 247, 250, 265 — both keys populated in correct locations.

```
PYTHONPATH=. .venv/bin/pytest tests/test_skill_importer.py -v
```
Result: All tests including TestDependencyParsing and TestZipScripts — 29 passed.

```
PYTHONPATH=. .venv/bin/pytest tests/test_security_scanner.py tests/test_skill_importer.py -q
```
Result: 63 passed — both test files fully green.

```
PYTHONPATH=. .venv/bin/pytest tests/ -q
```
Result: 825 passed, 1 skipped — no regressions.

## Self-Check: PASSED
