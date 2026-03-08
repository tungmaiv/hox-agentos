---
phase: 21-skill-platform-c-dependency-security-hardening
verified: 2026-03-08T00:00:00Z
status: passed
score: 12/12 must-haves verified
re_verification: false
gaps: []
human_verification: []
---

# Phase 21: Skill Platform C — Dependency & Security Hardening Verification Report

**Phase Goal:** Harden the skill platform's dependency security and tool access control — replace the ineffective author_verification scoring factor with real dependency and data-flow risk analysis, add an allowed-tools pre-gate to the executor, implement upstream change detection, and extend the importer to extract dependency information for scanner consumption.
**Verified:** 2026-03-08
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SecurityScanner.scan() computes a 6-factor weighted score summing to 100% | VERIFIED | `security_scanner.py` line 167–174: weights 0.25+0.20+0.20+0.05+0.20+0.10 |
| 2 | dependency_risk factor returns 0 when undeclared third-party imports are detected | VERIFIED | `_score_dependency_risk()` line 343–344: `if undeclared: return 0` |
| 3 | data_flow_risk factor returns a reduced score when sensitive-read + outbound-write pattern is found | VERIFIED | `_score_data_flow_risk()` line 392–395: `score -= 60` on exfiltration pattern |
| 4 | author_verification factor is removed — no reference in scan output | VERIFIED | `grep author_verification security_scanner.py` returns nothing; `TestWeightedScoring` asserts `"author_verification" not in report.factors` |
| 5 | A skill with allowed_tools=['email.fetch'] cannot call 'email.send' — SkillResult.success=False | VERIFIED | `executor.py` line 227–240: pre-gate raises `SkillStepError` for undeclared tool |
| 6 | allowed_tools=None or [] is permissive (backwards compatible) | VERIFIED | `executor.py` line 227: `if allowed_tools is not None and len(allowed_tools) > 0` — both None and [] skip the check |
| 7 | Blocked allowed_tools calls emit a structlog audit entry 'skill_allowed_tools_denied' | VERIFIED | `executor.py` line 229–236: `audit_logger.info("skill_allowed_tools_denied", ...)` with all required fields |
| 8 | allowed_tools check fires BEFORE get_tool() — check_tool_acl not called for denied tools | VERIFIED | Line 227 (allowed_tools check) precedes line 243 (get_tool) and line 248 (check_tool_acl) |
| 9 | SkillDefinition ORM model has a source_hash TEXT column (nullable) | VERIFIED | `skill_definition.py` line 96: `source_hash: Mapped[str | None] = mapped_column(Text, nullable=True)` |
| 10 | Migration 024 adds source_hash with down_revision=023 | VERIFIED | `024_skill_source_hash.py`: `revision = "024"`, `down_revision = "023"`, adds `sa.Column("source_hash", sa.Text, nullable=True)` |
| 11 | Celery beat fires check_skill_updates_task daily at 2am UTC | VERIFIED | `celery_app.py` line 51–53: `"check-skill-updates-daily"` entry with `crontab(hour=2, minute=0)` |
| 12 | SkillImporter.parse_skill_md() populates 'declared_dependencies' and import_from_zip() extracts scripts_content | VERIFIED | `importer.py` line 150–157 (frontmatter deps), line 236–247 (scripts_content), line 250–268 (requirements.txt fallback) |

**Score:** 12/12 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/skills/security_scanner.py` | 6-factor scoring with dependency_risk and data_flow_risk | VERIFIED | 415 lines; `_score_dependency_risk()` and `_score_data_flow_risk()` both present; hard veto at line 178 for undeclared imports |
| `backend/tests/test_security_scanner.py` | TestDependencyRisk (5 tests), TestDataFlowRisk (4 tests), updated TestWeightedScoring | VERIFIED | All three test classes present; TestDependencyRisk at line 227, TestDataFlowRisk at line 277 |
| `backend/skills/executor.py` | allowed_tools pre-gate in _run_tool_step(), audit log on denial | VERIFIED | Pre-gate at line 224–240; `audit_logger = get_audit_logger()` at module level |
| `backend/tests/test_skill_executor.py` | TestAllowedTools class covering 6 test cases | VERIFIED | TestAllowedTools at line 425 with full fixture setup |
| `backend/core/models/skill_definition.py` | source_hash TEXT column on SkillDefinition | VERIFIED | Line 96: `source_hash: Mapped[str | None] = mapped_column(Text, nullable=True)` |
| `backend/alembic/versions/024_skill_source_hash.py` | Migration 024 adding source_hash, down_revision=023 | VERIFIED | Correct revision chain; upgrade/downgrade both implemented |
| `backend/scheduler/tasks/check_skill_updates.py` | Daily Celery task with SHA-256 hash comparison | VERIFIED | 148 lines; `_check_all_skill_updates()`, `_check_single_skill()`, `_bump_version()` all implemented |
| `backend/tests/scheduler/test_check_skill_updates.py` | Unit tests including test_null_hash_stores_without_creating_review | VERIFIED | `test_null_hash_stores_without_creating_review` present at line 150 |
| `backend/skills/importer.py` | declared_dependencies parsing, scripts_content extraction, requirements.txt fallback | VERIFIED | SKSEC-01 blocks at lines 149–157 (parse_skill_md) and 236–268 (import_from_zip) |
| `backend/tests/test_skill_importer.py` | TestDependencyParsing (5 tests) and TestZipScripts (4 tests) | VERIFIED | TestDependencyParsing at line 357, TestZipScripts at line 413 |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `security_scanner.py` | `skill_data['scripts_content']` | `_score_dependency_risk()` reads scripts_content list | VERIFIED | Line 326: `scripts_content = skill_data.get("scripts_content", [])` |
| `security_scanner.py` | `sys.stdlib_module_names` | stdlib detection frozenset — Python 3.10+ | VERIFIED | Line 68: `_STDLIB_MODULES: frozenset[str] = sys.stdlib_module_names` |
| `executor.py` | `security.acl.check_tool_acl` | allowed_tools check fires first; check_tool_acl only reached if allowed | VERIFIED | Lines 227–240 (pre-gate) precede line 248 (check_tool_acl) |
| `executor.py` | `core.logging.get_audit_logger` | `audit_logger.info('skill_allowed_tools_denied', ...)` on denial | VERIFIED | Line 34: `audit_logger = get_audit_logger()`; line 229: event fired on denial |
| `celery_app.py` | `scheduler.tasks.check_skill_updates` | include list + beat_schedule with crontab(hour=2, minute=0) | VERIFIED | Lines 26–27 (include), lines 41 (task_routes), lines 50–53 (beat_schedule) |
| `check_skill_updates.py` | `core.models.skill_definition.SkillDefinition` | asyncio.run() wrapping async query; creates new SkillDefinition row on change | VERIFIED | `_check_single_skill()` creates new `SkillDefinition` row with `status="pending_review"` |
| `importer.py` | `security_scanner.py` | `skill_data['scripts_content']` and `skill_data['declared_dependencies']` consumed by scanner | VERIFIED | Scanner hard veto at line 178: `if factors["dependency_risk"] == 0 and skill_data.get("scripts_content")` → forces "reject" |
| `importer.py` | `scripts/requirements.txt inside ZIP` | Fallback: if no declared_dependencies in frontmatter, scan ZIP for scripts/requirements.txt | VERIFIED | Lines 250–268: reads requirements.txt, strips version specifiers |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SKSEC-01 | 21-04 | Scripts directory must declare dependencies; scanner blocks undeclared imports | SATISFIED | Importer extracts declared_dependencies and scripts_content; scanner hard veto forces "reject" for undeclared imports |
| SKSEC-02 | 21-02 | allowed-tools enforcement in SkillExecutor; denied calls logged to audit | SATISFIED | Pre-gate in `_run_tool_step()` at line 227; audit log at line 229; TestAllowedTools covers all cases |
| SKSEC-03 | 21-03 | Update checker Celery task re-fetches source_url, compares hash, creates pending_review on change | SATISFIED | `check_skill_updates.py` fully implemented; beat_schedule at 2am UTC; migration 024 adds source_hash |
| SKSEC-04 | 21-01 | SecurityScanner enhanced with dependency_risk (20%) and data_flow_risk (10%); author_verification removed | SATISFIED | 6-factor scoring verified; author_verification absent from code and test assertions |

All 4 phase requirements (SKSEC-01, SKSEC-02, SKSEC-03, SKSEC-04) are satisfied with verified implementations.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | — |

No stubs, placeholders, TODO/FIXME comments, empty implementations, or console.log-only functions were found in any of the modified files. All implementations are substantive.

---

## Human Verification Required

None. All phase goals are verifiable programmatically. The test suite (825 tests passing per SUMMARY.md) provides strong automated coverage of all behaviors.

---

## Gaps Summary

No gaps. All 12 observable truths verified. All 10 required artifacts exist, are substantive (not stubs), and are correctly wired. All 4 requirement IDs satisfied. No anti-patterns found.

Notable implementation quality points:
- Plan 21-04 auto-fixed a correctness bug discovered during TDD (weighted scoring could not force "reject" for undeclared imports at 0.20 weight; a hard veto was added)
- The allowed_tools pre-gate ordering (line 227 before line 243/248) correctly enforces that no DB lookup occurs on denied tools
- The null-baseline guard in check_skill_updates prevents spurious "Update available" flooding on first run after migration 024

---

_Verified: 2026-03-08_
_Verifier: Claude (gsd-verifier)_
