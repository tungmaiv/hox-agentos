---
phase: quick-6
plan: 01
subsystem: security
tags: [security-scanner, artifact-builder, frontend-gate, hybrid-llm, async]
key-decisions:
  - "SecurityScanner.scan() made async — all callers now use await"
  - "LLM review is one-way: final score = min(code_score, llm_adjusted_score) — LLM cannot raise trust"
  - "None-value filtering applied to all three merge paths in _extract_draft_from_response"
  - "Gate condition changed from !== 'approve' to === 'review' — reject is now a hard block with no UI escape hatch"
key-files:
  modified:
    - frontend/src/components/admin/security-report-card.tsx
    - backend/skills/security_scanner.py
    - backend/skill_repos/service.py
    - backend/api/routes/admin_skills.py
    - backend/agents/artifact_builder.py
    - backend/tests/skills/test_security_gate.py
    - backend/tests/test_skill_repos.py
    - backend/tests/test_skill_importer.py
    - backend/tests/test_security_scanner.py
metrics:
  completed: "2026-03-11"
  tasks: 2
  files: 9
  commits: 3
---

# Quick Task 6: Fix Phase 23 UAT Gaps (Reject Hard Block + Hybrid LLM Scanner)

Closes three Phase 23 UAT gaps: reject recommendation is now a hard block with no
activation path; SecurityScanner runs hybrid LLM review for skills scoring < 80;
null fields from LLM draft extraction no longer overwrite existing draft values.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix reject hard block + null draft filter | dcef076 | security-report-card.tsx, artifact_builder.py |
| 2 (RED) | Add failing tests for async hybrid LLM scanner | 762500e | test_security_scanner.py |
| 2 (GREEN) | Async hybrid LLM scanner implementation | 4b06a15 | security_scanner.py + 5 other files |

## Changes by File

### frontend/src/components/admin/security-report-card.tsx

Line 157 gate condition changed:
- Before: `{report.recommendation !== "approve" && (` — showed Approve & Activate for both "review" AND "reject"
- After: `{report.recommendation === "review" && (` — "reject" is now a hard block; button only appears for "review"

Also updated the comment from `{/* Approve & Activate (only for review/reject) */}` to `{/* Approve & Activate (only for review — reject is a hard block) */}`.

### backend/agents/artifact_builder.py

`_extract_draft_from_response()` now filters `None` values from all three merge paths before merging into `current_draft`:

- Primary path (code-fence JSON extraction): `filtered = {k: v for k, v in best.items() if v is not None}`
- Fallback tool-call-shaped blob path: `filtered_args = {k: v for k, v in args.items() if v is not None}`
- Fallback flat dict path: `filtered_parsed = {k: v for k, v in parsed.items() if v is not None}`

This prevents partial LLM extractions (where some fields are null) from overwriting previously filled draft values.

### backend/skills/security_scanner.py

`scan()` is now `async def`. Added `_llm_review()` async method:

- Skills scoring >= 80 on code analysis skip LLM (fast path, no extra latency)
- Skills scoring < 80 (and not hard-vetoed for undeclared imports) call `_llm_review()`
- Final score = `min(code_score, llm_adjusted_score)` — LLM can only lower trust
- LLM `risk_level="high"` forces `recommendation = "reject"` regardless of score
- LLM failures (network error, JSON parse failure) fall back to code-only score with warning log
- Added `import json` to module imports (was missing; `re` was already present)

### Updated callers of scanner.scan()

All three async FastAPI route functions in `admin_skills.py` updated to `await scanner.scan(...)`. The `skill_repos/service.py` caller also updated. Comment on the `builder_save` site updated from "synchronously" to accurate description.

### Test updates

- `test_security_scanner.py`: All 29 existing tests converted to `async def` with `await scanner.scan(...)`. Added `_unknown_source_skill()` helper and `TestHybridLLMReview` class with 5 new tests.
- `test_security_gate.py`: Added `AsyncMock` import; changed 3 mock sites from `MagicMock(return_value=...)` to `AsyncMock(return_value=...)`.
- `test_skill_repos.py`: Changed 3 mock sites from `MagicMock(return_value=...)` to `AsyncMock(return_value=...)`; updated assertion to `assert_awaited_once_with`.
- `test_skill_importer.py`: Changed integration test to `async def` and `await scanner.scan(skill_data)`.

## Test Results

```
Backend: 867 passed, 1 skipped, 28 warnings
TypeScript: no errors in security-report-card.tsx
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated mocks in test_security_gate.py and test_skill_repos.py**
- **Found during:** Task 2 GREEN (full suite run)
- **Issue:** Existing tests mocked `scanner.scan` as `MagicMock(return_value=...)` — not awaitable after scan() became async, causing 6 test failures
- **Fix:** Changed to `AsyncMock(return_value=...)` in both files; updated `assert_called_once_with` to `assert_awaited_once_with` in test_skill_repos.py
- **Files modified:** tests/skills/test_security_gate.py, tests/test_skill_repos.py
- **Commit:** 4b06a15

**2. [Rule 2 - Missing] Applied None-filter to fallback merge paths**
- **Found during:** Task 1 (reading the code)
- **Issue:** Plan specified fixing only the primary merge path (line 273-274), but the fallback paths (tool-call-shaped blob and flat dict) had the same None-overwrite risk
- **Fix:** Applied the same filter dict comprehension to all three paths
- **Files modified:** backend/agents/artifact_builder.py
- **Commit:** dcef076

## Self-Check: PASSED

All files exist. All commits verified:
- dcef076 (fix: reject hard block + null draft filter)
- 762500e (test: failing tests for async hybrid LLM scanner)
- 4b06a15 (feat: async hybrid LLM scanner)
