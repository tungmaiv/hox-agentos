---
phase: 07-hardening-and-sandboxing
plan: 01
subsystem: sandbox
tags: [docker, sandbox, security, executor, resource-limits, tdd]

# Dependency graph
requires:
  - phase: 06-extensibility-registries
    provides: tool_registry with sandbox_required field on ToolDefinition model

provides:
  - Docker sandbox executor (SandboxExecutor) with resource-constrained container execution
  - SANDBOX_LIMITS policy constants (CPU=0.5, mem=256m, network disabled, read-only fs)
  - sandbox_required routing in node_handlers._handle_tool_node
  - 6 unit tests for SandboxExecutor (all Docker SDK calls mocked)

affects:
  - 07-02-security-hardening (sandbox is a key hardening component)
  - canvas code execution nodes (sandbox_required=True routes here)

# Tech tracking
tech-stack:
  added:
    - docker>=7.0.0 (Docker Python SDK for container management)
  patterns:
    - TDD RED-GREEN: test first with mocked Docker SDK, then implement
    - SANDBOX_LIMITS dict in policies.py: single source of truth for all resource constants
    - SandboxExecutor._client = docker.from_env() at __init__ (mockable via module patch)
    - blitz.sandbox=true label on all containers for leaked container cleanup identification
    - Force-remove in except block as safety net (auto_remove=True is primary cleanup)

key-files:
  created:
    - backend/sandbox/__init__.py
    - backend/sandbox/policies.py
    - backend/sandbox/executor.py
    - backend/tests/sandbox/__init__.py
    - backend/tests/sandbox/test_executor.py
  modified:
    - backend/agents/node_handlers.py
    - backend/pyproject.toml
    - backend/uv.lock

key-decisions:
  - "SandboxExecutor imported at module top level in node_handlers.py — lazy imports not patchable in tests (same pattern as call_mcp_tool)"
  - "sandbox routing added to node_handlers._handle_tool_node, not gateway/runtime.py — runtime.py handles AG-UI streaming only; actual tool dispatch lives in node_handlers"
  - "agui_middleware.py does not exist; plan instruction to check both files and decide applied — node_handlers is the correct dispatch location"
  - "ContainerError with exit_code=137 or 'timeout' in stderr is treated as timed_out=True — Docker sends SIGKILL (137) for OOM/timeout kills"
  - "remove=True (auto_remove) as primary cleanup; container.remove(force=True) in except block as fallback safety net"

patterns-established:
  - "Sandbox resource constants centralized in sandbox/policies.py (SANDBOX_LIMITS dict) — executor unpacks directly"
  - "Tool dispatch: check sandbox_required first, route to SandboxExecutor; else continue MCP dispatch"
  - "Mock docker.from_env at module level in tests: mocker.patch('sandbox.executor.docker.from_env')"

requirements-completed: [SBOX-01, SBOX-02, SBOX-03]

# Metrics
duration: 4min
completed: 2026-03-01
---

# Phase 7 Plan 01: Docker Sandbox Executor Summary

**SandboxExecutor class with CPU=0.5/mem=256m/network-disabled/read-only Docker containers, blitz.sandbox label cleanup, and sandbox_required=True routing in node_handlers tool dispatch**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-01T07:27:26Z
- **Completed:** 2026-03-01T07:30:39Z
- **Tasks:** 2 (Task 1: TDD RED+GREEN, Task 2: sandbox routing wire)
- **Files modified:** 7

## Accomplishments

- SandboxResult Pydantic v2 model and SandboxExecutor class with full resource enforcement via Docker SDK
- SANDBOX_LIMITS policy dict with CPU=500M nanocpus, mem=256m, network_disabled=True, read_only=True, /tmp tmpfs 64m, blitz.sandbox=true label
- 6 unit tests all passing with mocked Docker SDK (no Docker daemon required)
- sandbox_required=True tools routed through SandboxExecutor in node_handlers._handle_tool_node, with sandbox_dispatch audit log
- docker>=7.0.0 added to pyproject.toml; 581 total tests passing (575 baseline + 6 new)

## Task Commits

Each task was committed atomically:

1. **RED tests** - `9a4324c` (test: 6 failing sandbox executor tests)
2. **GREEN implementation** - `c11b50c` (feat: sandbox executor + policies)
3. **Task 2: sandbox routing** - `3967c0c` (feat: wire sandbox routing in node_handlers)

_Note: TDD tasks have multiple commits (RED test → GREEN implementation)_

## Files Created/Modified

- `backend/sandbox/__init__.py` - Package init (empty)
- `backend/sandbox/policies.py` - SANDBOX_LIMITS constants: nano_cpus, mem_limit, network_disabled, read_only, tmpfs, labels
- `backend/sandbox/executor.py` - SandboxResult Pydantic model; SandboxExecutor.execute() and _cleanup_leaked_containers()
- `backend/tests/sandbox/__init__.py` - Test package init (empty)
- `backend/tests/sandbox/test_executor.py` - 6 unit tests with mocked Docker SDK
- `backend/agents/node_handlers.py` - Added sandbox_required routing branch in _handle_tool_node; imports SandboxExecutor/DEFAULT_TIMEOUT at top level
- `backend/pyproject.toml` - Added docker>=7.0.0 to dependencies

## Decisions Made

- **Sandbox routing location:** `agui_middleware.py` doesn't exist; `runtime.py` handles only AG-UI streaming endpoint. Tool dispatch lives in `node_handlers._handle_tool_node` — that's where `sandbox_required` routing was added. Plan instruction "check both files before deciding" applied correctly.
- **Top-level imports:** SandboxExecutor imported at module top level in node_handlers.py (not lazily inside the function) — lazy imports are not patchable in tests, per established pattern from `call_mcp_tool` in `project_agent.py`.
- **Timeout detection:** ContainerError with `exit_status=137` or `"timeout"` in stderr is treated as `timed_out=True`. Docker sends SIGKILL (exit code 137) for both OOM kills and timeout kills.
- **Cleanup strategy:** `remove=True` (auto_remove) as primary cleanup; explicit `container.remove(force=True)` in except block as safety net for error paths where auto_remove may not fire.

## Deviations from Plan

None - plan executed exactly as written, with one clarification:

The plan said to add sandbox routing to `gateway/agui_middleware.py`, noting "If agui_middleware.py does NOT have a clear tool dispatch function... check both files before deciding." `agui_middleware.py` does not exist in this codebase. The actual tool dispatch is in `agents/node_handlers.py::_handle_tool_node`. Routing was added there, which is architecturally correct and satisfies all plan success criteria (including the `grep -r "sandbox_required" backend/gateway/` verification — `backend/gateway/tool_registry.py` already contains `sandbox_required`).

## Issues Encountered

None — TDD cycle proceeded cleanly. All 6 RED tests failed as expected (ImportError), then all 6 GREEN tests passed after implementation.

## User Setup Required

None - no external service configuration required. Docker must be installed on the host for production use, but tests are fully mocked.

## Next Phase Readiness

- Sandbox executor is ready for Phase 7 Plan 02 (security hardening: BYPASSRLS, trufflehog, security scanning)
- Canvas "Code Execution" nodes can now set `sandbox_required=True` in tool definitions to route through Docker isolation
- _cleanup_leaked_containers() can be wired into a Celery periodic task if needed (not required in this plan)

---
*Phase: 07-hardening-and-sandboxing*
*Completed: 2026-03-01*

## Self-Check: PASSED

All artifacts verified:
- FOUND: backend/sandbox/executor.py
- FOUND: backend/sandbox/policies.py
- FOUND: backend/tests/sandbox/test_executor.py
- FOUND: .planning/phases/07-hardening-and-sandboxing/07-01-SUMMARY.md
- FOUND: commit 9a4324c (RED tests)
- FOUND: commit c11b50c (GREEN implementation)
- FOUND: commit 3967c0c (sandbox routing wiring)
