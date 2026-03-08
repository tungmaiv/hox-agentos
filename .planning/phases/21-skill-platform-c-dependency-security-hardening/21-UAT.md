---
status: complete
phase: 21-skill-platform-c-dependency-security-hardening
source: 21-01-SUMMARY.md, 21-02-SUMMARY.md, 21-03-SUMMARY.md, 21-04-SUMMARY.md
started: 2026-03-08T00:00:00Z
updated: 2026-03-08T00:00:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: [testing complete]

## Tests

### 1. Security Scanner — 6-Factor Scoring (No author_verification)
expected: Run a security scan on any skill. The result should include exactly 6 scoring factors: source_reputation, tool_scope, prompt_safety, complexity, dependency_risk, data_flow_risk. The old "author_verification" factor must NOT appear anywhere in the result.
result: pass
note: "Blocker (migration 024 not applied) resolved before retest. Fresh scan confirmed: 6 factors present, author_verification absent."

### 2. Security Scanner — Undeclared Import → Reject
expected: When a skill has Python scripts that import a third-party package (e.g. paramiko, requests) that is NOT listed in its declared_dependencies, the scanner must recommend "reject" — not "review" or "approve". The score alone cannot override this; rejection is mandatory for undeclared imports.
result: pass

### 3. Security Scanner — Clean Skill Scores Positively
expected: A skill with no Python scripts (or only stdlib imports like os, json) and no dangerous tools or credential patterns in its prompt template should score above 70 and receive recommendation "approve" or "review" (not "reject").
result: pass

### 4. Allowed-Tools Pre-Gate — Undeclared Tool Blocked
expected: A skill with allowed_tools=["email.fetch"] that tries to call "email.send" during execution should be blocked immediately. The system should NOT execute the step, and an audit log entry "skill_allowed_tools_denied" should be recorded with the skill name, the tool that was denied, and the declared allowed_tools list.
result: pass

### 5. Allowed-Tools Pre-Gate — Permissive When Not Declared
expected: A skill with no allowed_tools declaration (allowed_tools=None or absent) should continue to execute normally — all tools it calls go through the regular Gate 3 ACL, and the pre-gate does not block anything. Existing behavior is preserved.
result: pass

### 6. Daily Update Checker — Celery Beat Schedule Registered
expected: The Celery beat schedule includes "check-skill-updates-daily" configured to run at 2:00 AM UTC daily. This can be verified by checking the celery_app.py beat_schedule config or running `celery -A scheduler.celery_app inspect scheduled` against a running worker.
result: pass

### 7. Daily Update Checker — Changed Source Creates pending_review Row
expected: When the daily checker runs and detects that an imported skill's source URL content has changed (different SHA-256 hash), it creates a new SkillDefinition row with status="pending_review" and a patch-bumped version (e.g. 1.0.0 → 1.0.1). The admin skill catalog badge shows the pending review count increment.
result: pass

### 8. ZIP Import — Declared Dependencies Extracted
expected: When importing a skill ZIP that contains a SKILL.md with "dependencies: [requests, httpx]" in frontmatter, the imported skill record has declared_dependencies=["requests","httpx"]. If no frontmatter dependencies, but a scripts/requirements.txt exists with "requests==2.31.0", the skill record has declared_dependencies=["requests"] (version specifier stripped).
result: pass

### 9. ZIP Import — Undeclared Script Import Triggers Rejection
expected: When importing a skill ZIP with a scripts/helper.py that does "import paramiko" but paramiko is NOT in declared_dependencies (or requirements.txt), the security scanner rejects the skill with recommendation="reject" during the import flow. The skill is not saved as active.
result: pass

## Summary

total: 9
passed: 9
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "Admin skills page loads and skill security scanning works end-to-end"
  status: failed
  reason: "User reported: Admin skills page shows HTTP 500 — UndefinedColumnError: column skill_definitions.source_hash does not exist. Migration 024 not applied to the database."
  severity: blocker
  test: 1
  root_cause: "Migration 024 (024_skill_source_hash.py) adds source_hash column to skill_definitions. The ORM model was updated but migration was not applied to the running PostgreSQL instance. Every skills query now fails."
  artifacts:
    - path: "backend/alembic/versions/024_skill_source_hash.py"
      issue: "Migration exists but has not been run against the DB"
    - path: "backend/core/models/skill_definition.py"
      issue: "ORM model references source_hash column that does not exist in DB"
  missing:
    - "Run: docker exec blitz-backend .venv/bin/alembic upgrade head (or: just migrate)"
  debug_session: ""
