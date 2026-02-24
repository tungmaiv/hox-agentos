---
phase: 01-identity-and-infrastructure-skeleton
plan: "03"
subsystem: auth
tags: [rbac, acl, sqlalchemy, alembic, pgvector, sqlite, aiosqlite, structlog, pytest, tdd, security]

# Dependency graph
requires:
  - phase: 01-02
    provides: UserContext TypedDict (user_id UUID, roles list[str]) from JWT Gate 1; security/__init__.py package; conftest.py with test env vars
  - phase: 01-01
    provides: core/db.py (Base, async_session), core/logging.py (get_audit_logger), core/config.py Settings
provides:
  - ROLE_PERMISSIONS dict in security/rbac.py mapping 5 roles to permission sets (locked contract for Phase 2+)
  - has_permission(user_context, permission) Gate 2 RBAC check
  - get_permissions(roles) permission union utility
  - check_tool_acl(user_id, tool_name, session) Gate 3 per-user ACL with default-allow
  - log_tool_call(user_id, tool_name, allowed, duration_ms) structlog audit logging
  - ToolAcl SQLAlchemy ORM model in core/models/tool_acl.py
  - Alembic initial migration (revision 001) creating tool_acl table + pgvector + uuid-ossp
  - 36-test security suite: JWT (7) + RBAC (22) + ACL (7)
affects:
  - 01-04 (FastAPI routes will use has_permission() and check_tool_acl() to enforce all 3 gates)
  - 02+ (Agent tools will call check_tool_acl() from JWT user_id; RBAC permissions gated per tool call)
  - All agent/tool/memory operations in Phase 2-3 (consume UserContext.roles and UserContext.user_id)

# Tech tracking
tech-stack:
  added:
    - aiosqlite>=0.22.1 (dev dep — async SQLite driver for in-memory unit tests; no real PostgreSQL needed)
  patterns:
    - ROLE_PERMISSIONS dict with explicit permission enumeration (no inheritance chain — readable and testable)
    - Tool ACL default-allow policy (no row = allow; deny requires explicit row with allowed=False)
    - structlog audit logger writes to stdout via LoggerFactory; captured with capsys in tests (not caplog)
    - check_tool_acl() always receives user_id from get_current_user() JWT — never from request body (invariant)

key-files:
  created:
    - backend/security/rbac.py
    - backend/security/acl.py
    - backend/core/models/tool_acl.py
    - backend/alembic/versions/001_initial.py
    - backend/tests/test_rbac.py
    - backend/tests/test_acl.py
  modified:
    - backend/pyproject.toml (added aiosqlite dev dependency)
    - backend/tests/test_acl.py (fixed audit log test to use capsys instead of caplog)

key-decisions:
  - "ROLE_PERMISSIONS uses explicit permission enumeration per role — no inheritance chain. Simple, readable, testable."
  - "Tool ACL default policy is ALLOW (no row = True). Deny requires explicit row with allowed=False."
  - "structlog with LoggerFactory() writes to stdout. Use capsys in tests, not caplog, to capture audit log output."
  - "aiosqlite for ACL unit tests — no real PostgreSQL needed; SQLite supports all select/insert queries used."
  - "Alembic migration uses gen_random_uuid() for PostgreSQL UUID default (not uuid4() which is Python-side)."

patterns-established:
  - "has_permission(user_context, permission): Gate 2 check before any tool invocation"
  - "check_tool_acl(user_id, tool_name, session): Gate 3 check; user_id MUST come from get_current_user()"
  - "log_tool_call(): called after gate evaluation; fire-and-forget; never logs credentials"
  - "403 response format: {detail, permission_required, user_roles, hint} per CONTEXT.md requirements"

requirements-completed:
  - AUTH-03
  - AUTH-04
  - AUTH-05
  - AUTH-06

# Metrics
duration: 3min
completed: "2026-02-24"
---

# Phase 1 Plan 03: RBAC + Tool ACL + Audit Logging (Gates 2 and 3) Summary

**5-role RBAC permission mapping with per-user Tool ACL default-allow policy, structlog audit logging, ToolAcl SQLAlchemy model, Alembic initial migration enabling pgvector, and 36-test TDD suite covering all gate behaviors**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-24T14:12:16Z
- **Completed:** 2026-02-24T14:15:28Z
- **Tasks:** 2 (TDD: RED then GREEN)
- **Files modified:** 8

## Accomplishments

- `security/rbac.py` with locked 5-role `ROLE_PERMISSIONS` dict, `get_permissions(roles)`, and `has_permission(user_context, permission)` for Gate 2 enforcement
- `security/acl.py` with `check_tool_acl(user_id, tool_name, session)` default-allow Gate 3 check and `log_tool_call()` structlog audit logging (never logs credentials)
- `core/models/tool_acl.py` ToolAcl SQLAlchemy ORM model with unique (user_id, tool_name) constraint
- `alembic/versions/001_initial.py` initial migration creating tool_acl table, enabling pgvector extension and uuid-ossp
- 22 RBAC tests covering all 5 roles with positive and negative permission assertions
- 7 ACL tests using in-memory SQLite via aiosqlite — default-allow, explicit deny, explicit allow, user-scoped isolation, cross-tool independence, audit log fields

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): ToolAcl model, migration, and failing security tests** - `1bb0a0c` (test)
2. **Task 2 (GREEN): Implement RBAC, ACL, and audit logging** - `993090f` (feat)

**Plan metadata:** (see docs commit below)

_Note: TDD plan — RED commit then GREEN commit per TDD protocol_

## Files Created/Modified

- `backend/security/rbac.py` - ROLE_PERMISSIONS dict + has_permission() + get_permissions()
- `backend/security/acl.py` - check_tool_acl() Gate 3 + log_tool_call() audit
- `backend/core/models/tool_acl.py` - ToolAcl ORM model (user_id, tool_name, allowed, granted_by, created_at)
- `backend/alembic/versions/001_initial.py` - Initial migration: tool_acl table + pgvector + uuid-ossp + seed deny row
- `backend/tests/test_rbac.py` - 22 RBAC tests for all 5 roles + multi-role union + edge cases
- `backend/tests/test_acl.py` - 7 ACL tests with in-memory SQLite
- `backend/pyproject.toml` - Added aiosqlite>=0.22.1 to dev deps

## ROLE_PERMISSIONS Mapping (Full Reference for Phase 2+)

| Role | Permissions |
|------|-------------|
| `employee` | `chat`, `tool:email`, `tool:calendar`, `tool:project` |
| `manager` | All employee + `tool:reports`, `workflow:create` |
| `team-lead` | All manager + `workflow:approve` |
| `it-admin` | All permissions + `tool:admin`, `sandbox:execute`, `registry:manage` |
| `executive` | `chat`, `tool:reports` (read-only — no email/calendar/project) |

**Key behaviors:**
- Multi-role union: `get_permissions(["employee", "manager"])` returns union of both role sets
- Unknown roles: contribute zero permissions (deny by default)
- Empty roles: no permissions

## Tool ACL Behavior Reference

| Scenario | Result |
|----------|--------|
| No row in `tool_acl` for (user_id, tool_name) | `True` (default allow) |
| Row exists with `allowed=False` | `False` (explicit deny) |
| Row exists with `allowed=True` | `True` (explicit allow) |
| ACL for user A does not affect user B | True (parameterized on user_id) |
| ACL for `email.fetch` does not affect `calendar.read` | True (parameterized on tool_name) |

**Policy:** Open unless explicitly denied. To deny a user from a tool, insert a row with `allowed=False`.

## Audit Log Schema

Every tool call emits a structlog entry with these fields:

| Field | Type | Value |
|-------|------|-------|
| `event` | str | `"tool_call"` (constant) |
| `user_id` | str | UUID string from JWT sub (never object) |
| `tool` | str | Tool name (e.g. `"email.fetch"`) |
| `allowed` | bool | Final gate decision (True/False) |
| `duration_ms` | int | Gate evaluation time in milliseconds |

**Never logged:** `access_token`, `refresh_token`, `password`, or any credential value.

## Alembic Migration Reference

- **File:** `backend/alembic/versions/001_initial.py`
- **Revision ID:** `001`
- **Down revision:** `None` (initial migration)
- **Creates:** `tool_acl` table with index on `user_id` and unique constraint on `(user_id, tool_name)`
- **Enables:** `vector` extension (pgvector for future memory_facts vector search)
- **Enables:** `uuid-ossp` extension (PostgreSQL UUID generation)
- **Seeds:** One deny row for test user `00000000-0000-0000-0000-000000000001` + `email.fetch` (for Gate 3 dev testing)
- **Run:** `backend/.venv/bin/alembic upgrade head` (inside backend directory with DATABASE_URL set)

## 403 Response Format

As required by CONTEXT.md, all permission denials must return this structure:

```json
{
  "detail": "Permission denied",
  "permission_required": "tool:email",
  "user_roles": ["executive"],
  "hint": "Contact IT admin"
}
```

Implementation in routes (Plan 01-04 will wire this):

```python
if not has_permission(user_context, "tool:email"):
    raise HTTPException(
        status_code=403,
        detail={
            "detail": "Permission denied",
            "permission_required": "tool:email",
            "user_roles": user_context["roles"],
            "hint": "Contact IT admin",
        },
    )
```

## Decisions Made

- **ROLE_PERMISSIONS uses explicit enumeration**: No Python inheritance chain (e.g. no `MANAGER = EMPLOYEE | {...}`). Each role lists all its permissions explicitly. More readable, easier to audit, less surprising for new contributors.
- **Default-allow for Tool ACL**: No row means allowed. This simplifies onboarding (no need to pre-populate ACL for all users and all tools). IT admin only needs to add deny rows for exceptions.
- **aiosqlite for unit tests**: Avoids PostgreSQL dependency for unit tests. All ACL queries use standard SQL (select/insert/unique constraint) that SQLite supports. pgvector-specific SQL (e.g. `<->` distance queries) will be tested in integration tests.
- **capsys for audit log test**: structlog with `LoggerFactory()` writes to stdout — not to Python's `logging` module. Using `caplog` (which captures `logging` module output) would give empty strings. `capsys.readouterr()` captures the actual structlog stdout output correctly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Audit log test used `caplog` instead of `capsys` for structlog output**

- **Found during:** Task 2 (GREEN — running full test suite)
- **Issue:** `test_audit_log_contains_required_fields` used `caplog.at_level(logging.INFO)` to capture structlog output. structlog with `LoggerFactory()` writes directly to stdout via `sys.stdout`, not through Python's `logging` module. `caplog` only captures `logging` module records, so it was empty while the audit log was correctly emitted to captured stdout.
- **Fix:** Changed test to use `capsys` fixture and `capsys.readouterr()` to capture stdout. The log output (`tool_call allowed=True duration_ms=123 tool=email.fetch user_id=...`) is correctly captured and verified.
- **Files modified:** `backend/tests/test_acl.py`
- **Verification:** Test now passes; all 36 tests pass
- **Committed in:** `993090f` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug in test design)
**Impact on plan:** Test design correction. Implementation was correct from the start. No scope change.

## Issues Encountered

None beyond what is documented in Deviations above. Implementation matched the plan spec exactly.

## User Setup Required

None — all changes are backend code and unit tests. No external service configuration needed.

The Alembic migration (`001_initial.py`) requires a running PostgreSQL instance with pgvector installed to run `alembic upgrade head`. This will be done when the full Docker Compose stack is first started (Plan 01-04 or Phase 1 end-to-end test).

## Next Phase Readiness

- Gate 2 (RBAC) is complete: `has_permission(user_context, permission)` ready for any FastAPI route
- Gate 3 (Tool ACL) is complete: `check_tool_acl(user_id, tool_name, session)` ready for tool invocations
- Audit logging ready: `log_tool_call()` records every gate decision to structlog audit stream
- Plan 01-04 (FastAPI routes) can now wire all 3 gates: JWT → RBAC → Tool ACL → audit log
- Phase 2 agent tools will consume `UserContext.roles` (Gate 2) and `UserContext.user_id` (Gate 3)
- Alembic migration is ready to run against real PostgreSQL (requires pgvector-enabled PostgreSQL)

---
*Phase: 01-identity-and-infrastructure-skeleton*
*Completed: 2026-02-24*
