---
phase: 17-performance-embedding-sidecar
plan: "03"
subsystem: api
tags: [cachetools, ttl-cache, performance, acl, memory, user-instructions]

# Dependency graph
requires:
  - phase: 17-02
    provides: timed() context manager for latency logging

provides:
  - TTLCache for Tool ACL Gate 3 (60s TTL, keyed by user_id+tool_name)
  - TTLCache for episode threshold (60s TTL, keyed by user_id)
  - TTLCache for user instructions (60s TTL, keyed by user_id)
  - Cache invalidation on PUT /api/user/instructions
  - check_tool_acl_cached(), check_tool_acl_db(), clear_acl_cache() in security/acl.py
  - get_episode_threshold_db(), get_episode_threshold_cached(), clear_threshold_cache() in memory/medium_term.py
  - get_user_instructions_db(), get_user_instructions_cached(), clear_instructions_cache() in api/routes/user_instructions.py

affects:
  - 17-07 (JWKS lock, useSkills() hoist — PERF-12, PERF-13)

# Tech tracking
tech-stack:
  added:
    - cachetools==7.0.2 (TTLCache)
    - types-cachetools (dev, type stubs)
  patterns:
    - "cache-aside pattern: check cache → on miss, call DB function → store result"
    - "separate _db suffix function for raw DB fetch; _cached suffix for TTL-wrapped version"
    - "backward-compatible alias (get_user_instructions) delegates to _cached variant"
    - "cache invalidation on mutation: _instructions_cache.pop(user_id) on PUT"
    - "clear_*_cache() utility functions for test isolation"

key-files:
  created:
    - backend/tests/test_acl_cache.py
    - backend/tests/test_memory_caches.py
  modified:
    - backend/security/acl.py
    - backend/gateway/runtime.py
    - backend/memory/medium_term.py
    - backend/agents/master_agent.py
    - backend/api/routes/user_instructions.py
    - backend/tests/agents/test_master_agent_memory.py
    - backend/pyproject.toml
    - backend/uv.lock

key-decisions:
  - "cachetools TTLCache chosen over Redis: in-process cache is sufficient at ~100 user scale, no network hop"
  - "Cache keyed by user_id (not role) for ACL/instructions/threshold: per-user granularity matches security model"
  - "ACL cache max 500 entries: user_count(100) * tools_per_user(5) = 500 realistic upper bound"
  - "Patch target for get_episode_threshold_cached in tests must be agents.master_agent.get_episode_threshold_cached (import-site), not memory.medium_term.get_episode_threshold_cached (definition site)"
  - "_get_episode_threshold() private function in master_agent.py removed and replaced by get_episode_threshold_cached() from memory.medium_term — avoids duplicating DB read logic without caching"

patterns-established:
  - "TTLCache placement: declare module-level _*_cache variable after imports; clear_*_cache() for test reset"
  - "PUT handlers invalidate cache via dict.pop(user_id, None) — not .clear() — to avoid global invalidation"

requirements-completed: [PERF-09, PERF-10, PERF-11]

# Metrics
duration: 5min
completed: 2026-03-05
---

# Phase 17 Plan 03: Caching — Tool ACL, Episode Threshold, User Instructions Summary

**60s TTL in-process caches (cachetools) added to three hot DB paths: Tool ACL Gate 3, episode summarization threshold, and user custom instructions — eliminating repeated DB queries on every agent turn**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-05T12:33:08Z
- **Completed:** 2026-03-05T12:38:04Z
- **Tasks:** 6 (Tasks 1-6)
- **Files modified:** 8

## Accomplishments

- Installed `cachetools==7.0.2` and `types-cachetools` dev dependency
- Added `check_tool_acl_cached()` to `security/acl.py` with 60s TTL, 500 entry max; wired into `gateway/runtime.py` Gate 3
- Added `get_episode_threshold_cached()` and `get_episode_threshold_db()` to `memory/medium_term.py`; removed duplicate `_get_episode_threshold()` from `master_agent.py`
- Added `get_user_instructions_cached()`, `get_user_instructions_db()` to `api/routes/user_instructions.py`; cache invalidated on PUT
- 5 new tests: 3 in `test_acl_cache.py`, 2 in `test_memory_caches.py`; all existing tests updated for renamed/relocated functions

## Task Commits

Each task was committed atomically:

1. **Task 1: Install cachetools** - `2194e2c` (chore)
2. **Tasks 2+3: Write + implement Tool ACL cache (PERF-09)** - `9ba3bc8` (feat)
3. **Tasks 4+5+6: Write + implement episode threshold and user instructions caches (PERF-10, PERF-11)** - `89e3541` (feat)

## Files Created/Modified

- `backend/security/acl.py` — Added `_acl_cache`, `check_tool_acl_cached()`, `clear_acl_cache()`
- `backend/gateway/runtime.py` — Gate 3 now calls `check_tool_acl_cached` instead of `check_tool_acl`
- `backend/memory/medium_term.py` — Added `_threshold_cache`, `get_episode_threshold_db()`, `get_episode_threshold_cached()`, `clear_threshold_cache()`
- `backend/agents/master_agent.py` — Removed `_get_episode_threshold()`, added import + call to `get_episode_threshold_cached()`
- `backend/api/routes/user_instructions.py` — Added `_instructions_cache`, `get_user_instructions_db()`, `get_user_instructions_cached()`, `clear_instructions_cache()`; PUT handler invalidates cache
- `backend/tests/test_acl_cache.py` — 3 new tests for ACL cache behavior
- `backend/tests/test_memory_caches.py` — 2 new tests for episode threshold and instructions cache
- `backend/tests/agents/test_master_agent_memory.py` — Updated 5 tests for renamed threshold function

## Decisions Made

- Used `cachetools.TTLCache` (not Redis): in-process cache is sufficient for ~100 users — no network round-trip overhead
- Patch target for `get_episode_threshold_cached` in `master_agent` tests must be `agents.master_agent.get_episode_threshold_cached` (the import site), not `memory.medium_term.get_episode_threshold_cached` (the definition site)
- `_get_episode_threshold()` private function fully removed from `master_agent.py` — the cached version in `memory.medium_term` supersedes it with caching built in

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated `test_master_agent_memory.py` tests that patched the removed `_get_episode_threshold`**

- **Found during:** Task 5+6 (full suite run)
- **Issue:** Three tests patched `agents.master_agent._get_episode_threshold` which was removed; two tests imported `_get_episode_threshold` directly from `master_agent` (no longer exists)
- **Fix:** Updated three save_memory tests to patch `agents.master_agent.get_episode_threshold_cached`; rewrote two `_get_episode_threshold` tests to test `get_episode_threshold_db` from `memory.medium_term` directly (no session factory mock needed)
- **Files modified:** `backend/tests/agents/test_master_agent_memory.py`
- **Verification:** All 12 tests in the file pass; full suite 737 passed
- **Committed in:** `89e3541` (part of Task 4-6 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 bug — broken tests from renamed function)
**Impact on plan:** Necessary correctness fix. No scope creep.

## Issues Encountered

- The three `_save_memory_node` tests used `patch("agents.master_agent._get_episode_threshold")` — after removing that function and replacing with an import, the patch target changed to `"agents.master_agent.get_episode_threshold_cached"`. Standard Python mock patch-at-import-site rule.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All three hot DB paths now have 60s TTL caches; tool ACL Gate 3 no longer queries DB on every agent turn
- 737 tests passing (baseline was 732)
- Plan 17-07 can proceed with JWKS asyncio.Lock and useSkills() hoist (PERF-12, PERF-13)

## Self-Check: PASSED

All files and commits verified:
- `backend/tests/test_acl_cache.py` - FOUND
- `backend/tests/test_memory_caches.py` - FOUND
- `.planning/phases/17-performance-embedding-sidecar/17-03-SUMMARY.md` - FOUND
- `2194e2c` (chore: cachetools dep) - FOUND
- `9ba3bc8` (feat: ACL cache PERF-09) - FOUND
- `89e3541` (feat: threshold + instructions caches PERF-10/11) - FOUND

---
*Phase: 17-performance-embedding-sidecar*
*Completed: 2026-03-05*
