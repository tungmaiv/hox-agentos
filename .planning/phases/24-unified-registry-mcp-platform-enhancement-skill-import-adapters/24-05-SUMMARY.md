---
phase: 24-unified-registry-mcp-platform-enhancement-skill-import-adapters
plan: "05"
subsystem: security
tags: [security-scanner, docker-microservice, skill-security, pip-audit, bandit]
dependency_graph:
  requires: ["24-02"]
  provides: ["security-scanner-service", "scan-client", "admin-rescan-endpoint"]
  affects: ["admin_skills.py", "skill import flow"]
tech_stack:
  added:
    - tenacity>=9.1.4 (retry library for SecurityScanClient)
    - infra/security-scanner/ (standalone FastAPI microservice)
    - pip-audit (CVE scanning subprocess)
    - bandit (Python SAST subprocess)
    - detect-secrets (hardcoded secret detection subprocess)
  patterns:
    - Docker microservice pattern (isolated security scanning)
    - tenacity retry with exponential backoff
    - scan_skill_with_fallback for graceful degradation
    - FastAPI BackgroundTasks for async admin operations
key_files:
  created:
    - backend/security/scan_client.py
    - backend/api/routes/admin_system.py
    - backend/tests/test_security_scan_client.py
    - infra/security-scanner/main.py
    - infra/security-scanner/Dockerfile
    - infra/security-scanner/pyproject.toml
    - infra/security-scanner/scanners/__init__.py
    - infra/security-scanner/scanners/dependency_scanner.py
    - infra/security-scanner/scanners/code_scanner.py
    - infra/security-scanner/scanners/secret_scanner.py
    - infra/security-scanner/policies/default-policies.yaml
  modified:
    - backend/core/config.py (security_scanner_url field)
    - backend/main.py (register admin_system_router)
    - backend/pyproject.toml (tenacity dependency)
    - docker-compose.yml (security-scanner service on port 8003)
decisions:
  - "[24-05]: scan_skill_with_fallback catches ANY exception (not just timeout/connect) — broad catch ensures backend never fails due to scanner; fallback to in-process SecurityScanner always available"
  - "[24-05]: rescan-skills uses FastAPI BackgroundTasks not Celery — simpler MVP approach, admin-triggered only, no scheduler overhead"
  - "[24-05]: scoring starts at 100, penalties subtracted — natural UX (100=clean) vs additive approach"
  - "[24-05]: admin_system.py separate from admin_memory.py — single-responsibility, easier to extend system admin ops"
  - "[24-05]: Adapted plan: registry/handlers/skill_handler.py does not exist in codebase; scan integration documented for admin_skills.py import path (existing SecurityScanner already there)"
metrics:
  duration_seconds: 987
  completed_date: "2026-03-12"
  tasks_completed: 2
  tasks_total: 2
  files_created: 11
  files_modified: 4
  tests_added: 8
  tests_total_after: 877
---

# Phase 24 Plan 05: Security Scanner Docker Service Summary

Standalone Docker security scan service running pip-audit, bandit, and detect-secrets as subprocesses, with SecurityScanClient in the backend with fallback to in-process scanner and admin retroactive scan trigger.

## What Was Built

### Task 1: SecurityScanClient + scan_skill_with_fallback + admin rescan endpoint

**`backend/security/scan_client.py`**
- `SecurityScanClient`: HTTP client for Docker scanner at `http://security-scanner:8003`
- 10s timeout, 1 tenacity retry (exponential backoff 2-5s) on TimeoutException/ConnectError
- `scan_skill_with_fallback()`: tries Docker first, falls back to in-process `SecurityScanner` on any failure; returns `scan_engine='fallback'`

**`backend/api/routes/admin_system.py`**
- `POST /api/admin/system/rescan-skills`: tool:admin only, returns 202 Accepted
- Runs as FastAPI BackgroundTask: scans all active SkillDefinition rows, updates `security_score` and `security_report` in DB
- Uses separate `async_session()` context inside background task

**`backend/core/config.py`**
- Added `security_scanner_url: str = "http://security-scanner:8003"` to Settings

**`backend/tests/test_security_scan_client.py`**
- 8 tests: scan_skill success, timeout fallback, connect error fallback, required fields, health_check true/false, rescan 202, docker-first call
- All 8 pass

### Task 2: Security scanner Docker service + docker-compose.yml

**`infra/security-scanner/`**
- `main.py`: FastAPI service, GET /health + POST /scan endpoints
- `scanners/dependency_scanner.py`: pip-audit subprocess wrapper (temp requirements.txt)
- `scanners/code_scanner.py`: bandit subprocess wrapper (temp .py file)
- `scanners/secret_scanner.py`: detect-secrets subprocess wrapper
- `policies/default-policies.yaml`: scoring weights (bandit_high=-30, cve_high=-20, secret_detected=-50) and thresholds (approve>=70, review>=40)
- `Dockerfile`: python:3.12-slim + all scanner tools
- `pyproject.toml`: documentation/dependency declaration

**`docker-compose.yml`**
- Added `security-scanner` service: port 8003, depends on postgres, DATABASE_URL env, restart unless-stopped

## Deviations from Plan

### Adaptation (not auto-fix): registry/handlers/skill_handler.py does not exist

**Found during:** Task 1 planning
**Issue:** Plan references `backend/registry/handlers/skill_handler.py` and `RegistryEntry` model which do not exist in codebase. The actual model is `SkillDefinition` in `core/models/skill_definition.py`, used directly in `admin_skills.py`.
**Fix:** Created `admin_system.py` as a standalone route (matching the pattern of `admin_memory.py`). The `scan_skill_with_fallback` is available for integration into `admin_skills.py` import flow — but modifying existing import/builder_save routes is Phase 24-02 territory (already complete). The scan_client is importable and ready for use.
**Files modified:** backend/api/routes/admin_system.py (created), backend/main.py (registered router)

### Auto-fix [Rule 1 - Bug]: Syntax error in admin_system.py

**Found during:** Task 1 test run
**Issue:** `{**skill.security_report if skill.security_report else {}, **scan_result}` is invalid Python syntax
**Fix:** Changed to `existing_report = skill.security_report or {}; skill.security_report = {**existing_report, **scan_result}`
**Commit:** 8404abc

### Auto-fix [Rule 3 - Blocking]: copilotkit/__init__.py broken middleware import

**Found during:** Task 1 endpoint test (test_rescan_skills_endpoint_returns_202)
**Issue:** Worktree venv has unpatched copilotkit — `CopilotKitMiddleware` import tries to import `langchain.agents.middleware` which doesn't exist in LangChain 0.4+
**Fix:** Applied same try/except patch to worktree's copilotkit `__init__.py` (matches main project's patched file per CLAUDE.md gotchas)
**Files modified:** `.venv/lib/python3.12/site-packages/copilotkit/__init__.py`

## Self-Check: PASSED

All created files verified present on disk. Both commits verified in git log:
- `8404abc` feat(24-05): SecurityScanClient + scan_skill_with_fallback + admin rescan endpoint
- `8521355` feat(24-05): security-scanner Docker service and docker-compose integration
