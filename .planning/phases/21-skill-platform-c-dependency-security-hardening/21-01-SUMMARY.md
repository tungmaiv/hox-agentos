---
phase: 21-skill-platform-c-dependency-security-hardening
plan: "01"
subsystem: skills/security
tags: [security-scanner, tdd, scoring, dependency-risk, data-flow-risk]
dependency_graph:
  requires: []
  provides: [SecurityScanner 6-factor scoring, dependency_risk factor, data_flow_risk factor]
  affects: [backend/skills/security_scanner.py, backend/api/routes/admin_skills.py, backend/skills/skill_repos/service.py]
tech_stack:
  added: [ast, sys.stdlib_module_names]
  patterns: [TDD red-green, AST import analysis, weighted scoring]
key_files:
  modified:
    - backend/skills/security_scanner.py
    - backend/tests/test_security_scanner.py
decisions:
  - "[21-01]: author_verification removed — always returned 50 (no security value); replaced by two substantive factors"
  - "[21-01]: _STDLIB_MODULES uses sys.stdlib_module_names (Python 3.10+) — frozenset, fast membership test"
  - "[21-01]: undeclared third-party import returns 0 immediately — conservative default for unknown code"
  - "[21-01]: exfiltration detection: sensitive-read AND outbound-write pattern reduces score by 60 (not either alone)"
metrics:
  duration_minutes: 5
  completed_date: "2026-03-08"
  tasks_completed: 1
  files_changed: 2
---

# Phase 21 Plan 01: Security Scanner Factor Replacement Summary

**One-liner:** Replaced author_verification (always 50) with dependency_risk (AST undeclared import detection) and data_flow_risk (exfiltration pattern detection), rebalancing to 6 factors at 25/20/20/5/20/10%.

## What Was Built

### SecurityScanner — 6-Factor Weighted Scoring

Replaced `_score_author_verification()` (stub always returning 50) with two substantive security factors:

**`_score_dependency_risk(skill_data)`** (20% weight):
- Uses `ast.parse()` to extract all imported module names from attached Python scripts
- Filters out stdlib modules via `sys.stdlib_module_names` (Python 3.10+)
- If any third-party import is undeclared → return 0 immediately (hard fail)
- If dangerous packages declared (requests, httpx, paramiko, etc.) → 20-point penalty each
- Bloat score by dependency count: 0→100, 1-3→80, 4-10→50, 10+→20

**`_score_data_flow_risk(skill_data)`** (10% weight):
- No procedure_json → 100 (instructional skills are safe)
- Sensitive-read tool (email.fetch, crm.get, etc.) + outbound-write tool (http.post, sandbox.run) in same procedure → -60
- Credential pattern in prompt_template (api_key, password, token, Bearer) → -30
- Admin tool in procedure → -40; sandbox tool → -20

**New weight distribution** (sums to 100%):
- source_reputation: 30% → 25%
- tool_scope: 25% → 20%
- prompt_safety: 25% → 20%
- complexity: 10% → 5%
- dependency_risk: NEW 20%
- data_flow_risk: NEW 10%

### Test Coverage Added

**TestDependencyRisk** (5 tests):
- `test_no_scripts_returns_100` — no scripts_content → factor = 100
- `test_undeclared_import_rejected` — undeclared import requests → factor = 0
- `test_declared_import_scores_positive` — declared import → factor > 0
- `test_dangerous_package_penalty` — paramiko declared → factor < 100
- `test_stdlib_import_not_penalized` — import os → stdlib → factor = 100

**TestDataFlowRisk** (4 tests):
- `test_instructional_skill_returns_100` — no procedure_json → factor = 100
- `test_exfiltration_pattern_detected` — email.fetch + http.post → factor ≤ 40
- `test_credential_pattern_in_template` — api_key in prompt → factor ≤ 70
- `test_clean_procedure_full_score` — read-only, clean prompt → factor = 100

**TestWeightedScoring** updated: 6-factor formula, asserts `author_verification` not in `factors`.

## Commits

| Commit | Type | Description |
|--------|------|-------------|
| 7ad6bf6 | test(21-01) | Add failing tests for dependency_risk and data_flow_risk (RED) |
| f9c613f | feat(21-01) | Replace author_verification with dependency_risk and data_flow_risk (GREEN) |

## Verification

All verification criteria from the plan pass:

- `PYTHONPATH=. .venv/bin/pytest tests/test_security_scanner.py -v` — 28 tests pass
- `grep "author_verification" backend/skills/security_scanner.py` — returns nothing (removed)
- Both `dependency_risk` and `data_flow_risk` present in `scan()` method
- Weights `0.25/0.20/0.20/0.05/0.20/0.10` confirmed in source
- Full suite: 816 passed, 1 skipped (no regressions)

## Deviations from Plan

None — plan executed exactly as written. TDD flow: RED (test commit 7ad6bf6) → GREEN (impl commit f9c613f).

## Self-Check: PASSED

- `/home/tungmv/Projects/hox-agentos/backend/skills/security_scanner.py` — exists with 6-factor scoring
- `/home/tungmv/Projects/hox-agentos/backend/tests/test_security_scanner.py` — exists with TestDependencyRisk, TestDataFlowRisk
- Commit 7ad6bf6 — FOUND (test RED)
- Commit f9c613f — FOUND (impl GREEN)
- 28 tests pass, 816 total passing
