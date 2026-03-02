---
phase: 09-tech-debt-code-fixes
plan: "01"
subsystem: api
tags: [tool-registry, cache, admin-tools, fastapi, pytest]

# Dependency graph
requires:
  - phase: 06-extensibility-registries
    provides: tool_registry.py with in-process TTL cache and admin_tools.py CRUD routes
provides:
  - invalidate_tool_cache_entry(name) function for targeted single-entry cache eviction
  - Cache eviction wired into patch_tool_status() and activate_tool_version() admin routes
  - Corrected list_templates docstring (removed false "no JWT required" / "public read" claims)
  - 3 regression tests guarding against cache staleness regressions (EXTD-03/05)
affects: [10-optional-tech-debt-closure]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Targeted cache eviction: _tool_cache.pop(name, None) after admin status mutations — avoids global TTL reset while ensuring immediate consistency"

key-files:
  created: []
  modified:
    - backend/gateway/tool_registry.py
    - backend/api/routes/admin_tools.py
    - backend/api/routes/workflows.py
    - backend/tests/api/test_admin_tools.py
    - backend/tests/test_tool_registry_db.py

key-decisions:
  - "Targeted eviction (invalidate_tool_cache_entry) not global flush (invalidate_tool_cache) — preserves valid cache entries for other tools, only evicts the one that changed"
  - "Cache key is tool.name (string) for all versions — all versions of the same tool share a cache key, so evicting by name correctly invalidates all version data simultaneously"
  - "bulk_status_update() intentionally NOT patched — requires pre-fetch of tool names, out of scope per RESEARCH.md open question; deferred to phase 10"

patterns-established:
  - "Pattern: after any DB mutation that changes tool active/status state, call invalidate_tool_cache_entry(tool.name) immediately before returning from the route handler"

requirements-completed:
  - EXTD-03
  - EXTD-05

# Metrics
duration: 3min
completed: 2026-03-02
---

# Phase 9 Plan 01: Tool Cache Invalidation Fix Summary

**Targeted per-entry cache eviction wired into admin tool status/version routes, eliminating 60-second stale-cache window after disable or version switch**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-01T18:30:22Z
- **Completed:** 2026-03-01T18:33:13Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Added `invalidate_tool_cache_entry(name)` to `tool_registry.py` — uses `_tool_cache.pop(name, None)` for immediate targeted eviction without touching the global TTL timestamp
- Wired cache eviction into both `patch_tool_status()` and `activate_tool_version()` in `admin_tools.py` — disabled/version-switched tools are no longer callable for up to 60s
- Fixed inaccurate `list_templates` docstring in `workflows.py` — removed false "no JWT required" / "public read" claims (the route uses `get_user_db` which does require JWT)
- Added 3 regression tests: 2 integration tests in `test_admin_tools.py` and 1 unit test in `test_tool_registry_db.py`

## Task Commits

Each task was committed atomically:

1. **Task 1: Add invalidate_tool_cache_entry() and wire into admin routes** - `fb0bf65` (feat)
2. **Task 2: Write regression tests for cache invalidation** - `ef77128` (test)

**Plan metadata:** (docs commit to follow)

## Files Created/Modified
- `backend/gateway/tool_registry.py` — Added `invalidate_tool_cache_entry(name: str)` function after `invalidate_tool_cache()` (purely additive)
- `backend/api/routes/admin_tools.py` — Added `from gateway.tool_registry import invalidate_tool_cache_entry` import; added call sites in `patch_tool_status()` and `activate_tool_version()`
- `backend/api/routes/workflows.py` — Fixed `list_templates` docstring and module-level docstring entry from "public read" to "requires JWT"
- `backend/tests/api/test_admin_tools.py` — Added `test_patch_status_invalidates_cache` and `test_activate_version_invalidates_cache`
- `backend/tests/test_tool_registry_db.py` — Added `test_cache_entry_eviction`

## Decisions Made
- Targeted eviction (not global flush): `invalidate_tool_cache_entry()` uses `_tool_cache.pop(name, None)` and deliberately does NOT touch `_tool_cache_timestamp`. Other tools' cache entries remain valid — only the mutated tool is evicted. This avoids unnecessary DB refreshes triggered by unrelated tool admin operations.
- Cache key is always `tool.name` (string), not `tool.id` or version — consistent with how `_refresh_tool_cache()` populates `_tool_cache`. Evicting by name correctly handles all versions since they share the same key.
- `bulk_status_update()` not patched — the RESEARCH.md open question flags this as requiring a pre-fetch of tool names before the bulk UPDATE statement. Out of scope for this plan; deferred.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
None — all tests passed immediately on first run.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- EXTD-03 and EXTD-05 requirements are closed
- Phase 09 Plan 02 can proceed (next tech-debt items)
- Full test suite: 598 passed, 1 skipped (up from 258 baseline — suite has grown across phases)

---
*Phase: 09-tech-debt-code-fixes*
*Completed: 2026-03-02*
