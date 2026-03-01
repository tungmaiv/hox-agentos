---
status: complete
phase: 07-hardening-and-sandboxing
source: [07-01-SUMMARY.md, 07-02-SUMMARY.md, 07-03-SUMMARY.md, 07-04-SUMMARY.md]
started: 2026-03-01T16:00:00Z
updated: 2026-03-01T16:10:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Sandbox unit tests pass
expected: |
  Run the sandbox executor unit tests:
    cd /home/tungmv/Projects/hox-agentos/backend
    PYTHONPATH=. .venv/bin/pytest tests/sandbox/ -v

  You should see exactly 6 tests collected and all pass.
  No Docker daemon is required — all SDK calls are mocked.
result: pass

### 2. Sandbox resource limits are correct
expected: |
  Open backend/sandbox/policies.py and verify SANDBOX_LIMITS contains:
    - nano_cpus: 500_000_000  (= 0.5 CPU cores)
    - mem_limit: "256m"
    - network_disabled: True
    - read_only: True
    - tmpfs: {"/tmp": "size=64m,mode=777"}
    - labels: {"blitz.sandbox": "true"}

  And DEFAULT_TIMEOUT = 30, MAX_TIMEOUT = 120 are present.
result: pass

### 3. Sandbox routing wired in node_handlers
expected: |
  SandboxExecutor imported at module top-level (line 30); sandbox_required
  branch at line 143 routes to SandboxExecutor.execute() when True.
result: pass

### 4. Cross-user isolation pen tests pass in isolation
expected: |
  PYTHONPATH=. .venv/bin/pytest tests/security/test_isolation.py -v --tb=short
  → 5 passed, 1 skipped (pgvector skip intentional)
result: pass

### 5. RLS migration covers 6 tables
expected: |
  016_rls_policies.py: ENABLE + FORCE RLS on 6 tables, USING clause with
  current_setting, WITH CHECK INSERT policy, BYPASSRLS TO blitz,
  SQLite guard present.
result: pass

### 6. Git history is clean of secrets
expected: |
  trufflehog git file://. --only-verified → verified_secrets: 0,
  unverified_secrets: 0 across ~2260 chunks.
result: pass

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
