---
phase: quick-3
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/agents/master_agent.py
  - backend/core/prompts.py
  - backend/tests/test_skill_export.py
  - frontend/src/lib/api-client.ts
  - frontend/src/app/admin/layout.tsx
autonomous: true
requirements:
  - DEBT-01
must_haves:
  truths:
    - "update_agent_last_seen dead-code TODO comment is removed and function has a clear forward-compatibility docstring"
    - "serverFetch dead-code TODO comment is removed and function has a clear docstring"
    - "prompts.py docstring example no longer references deleted intent_classifier.md"
    - "admin/layout.tsx denies access when session exists but has no roles (tightened frontend guard)"
    - "test_skill_export.py emits no RuntimeWarning about unawaited coroutine"
    - "All 718 backend tests still pass (no regressions)"
  artifacts:
    - path: "backend/agents/master_agent.py"
      provides: "update_agent_last_seen with clean docstring, no dead-code TODO"
    - path: "backend/core/prompts.py"
      provides: "Module docstring referencing only existing prompt files"
    - path: "backend/tests/test_skill_export.py"
      provides: "test_export_route_returns_zip_for_existing_skill using AsyncMock correctly"
    - path: "frontend/src/lib/api-client.ts"
      provides: "serverFetch with clean forward-compatibility docstring, no dead-code TODO"
    - path: "frontend/src/app/admin/layout.tsx"
      provides: "allowAccess = hasAdminRole only (no allRoles.length === 0 bypass)"
  key_links:
    - from: "backend/tests/test_skill_export.py"
      to: "api.routes.admin_skills._require_registry_manager"
      via: "AsyncMock return_value"
      pattern: "AsyncMock.*return_value.*mock_user"
---

<objective>
Fix 5 actionable tech debt items identified in the v1.2 milestone audit. Item 4 (sub-agent .md files) is intentionally skipped — it is informational only and no code change is warranted.

Purpose: Clean up dead-code comments, stale docstring examples, a security-loosening frontend fallback, and an unawaited-coroutine warning so the codebase is easier to maintain and test output stays clean.
Output: 5 files modified, zero regressions, no RuntimeWarning from test suite.
</objective>

<execution_context>
@/home/tungmv/.claude/get-shit-done/workflows/execute-plan.md
@/home/tungmv/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/v1.2-MILESTONE-AUDIT.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Remove dead-code TODOs from master_agent.py and api-client.ts, fix stale prompts.py docstring</name>
  <files>backend/agents/master_agent.py, backend/core/prompts.py, frontend/src/lib/api-client.ts</files>
  <action>
Three targeted edits — each is a comment/docstring change only, no logic changes:

**backend/agents/master_agent.py — line 775:**
Replace:
```
# TODO: verify dead — update_agent_last_seen has no production callers; only called from tests.
# Designed for future wiring when dynamic agent dispatch logs last_seen_at to agent_definitions.
async def update_agent_last_seen(agent_name: str, session: AsyncSession) -> None:
    """
    Update last_seen_at on an agent after successful dispatch.

    Batched: only updates if last_seen_at is older than 60s or NULL,
    to avoid excessive DB writes on high-frequency agent invocations.
    """
```
With:
```
async def update_agent_last_seen(agent_name: str, session: AsyncSession) -> None:
    """
    Update last_seen_at on an agent after successful dispatch.

    Batched: only updates if last_seen_at is older than 60s or NULL,
    to avoid excessive DB writes on high-frequency agent invocations.

    Forward-compatibility: no production callers yet. Called from tests to validate the
    batching logic. Wire into the agent dispatch path when dynamic agent routing
    needs last_seen_at tracking in agent_definitions.
    """
```

**backend/core/prompts.py — module docstring, line 12:**
Replace:
```
    # With Jinja2-style {{ var }} substitution
    prompt = load_prompt("intent_classifier", message="check my emails")
```
With:
```
    # With Jinja2-style {{ var }} substitution
    prompt = load_prompt("master_agent")  # see backend/prompts/*.md for available prompts
```
(intent_classifier.md was deleted when the router was removed in Phase 11 DEBT-01. The docstring example must reference an existing file to avoid FileNotFoundError if copy-pasted.)

**frontend/src/lib/api-client.ts — line 44-46:**
Replace:
```
// TODO: verify dead — serverFetch is not imported by any Server Component yet.
// Designed for use in Server Components that need JWT-authenticated backend calls.
// Safe to keep: low overhead, no side-effects. Remove if still unused after Phase 12.
```
With:
```
// Forward-compatibility: serverFetch is not yet used by any Server Component.
// Designed for use in Server Components that need JWT-authenticated backend calls.
// auth.ts sets accessToken on the session for this purpose (see auth.ts:178).
```
(Phase 12 has passed — Phase 13 added local auth with accessToken also set on credentials session — function is still valid and safe to keep without a removal deadline.)
  </action>
  <verify>
    <automated>cd /home/tungmv/Projects/hox-agentos/backend && grep -n "TODO: verify dead" agents/master_agent.py core/prompts.py; echo "exit:$?"</automated>
  </verify>
  <done>
    - grep finds zero "TODO: verify dead" matches in master_agent.py and core/prompts.py
    - prompts.py module docstring example references master_agent (not intent_classifier)
    - api-client.ts has no "TODO: verify dead" comment
    - No logic changes in any of the three files
  </done>
</task>

<task type="auto">
  <name>Task 2: Tighten admin/layout.tsx frontend RBAC guard and fix test_skill_export.py RuntimeWarning</name>
  <files>frontend/src/app/admin/layout.tsx, backend/tests/test_skill_export.py</files>
  <action>
**frontend/src/app/admin/layout.tsx — line 71-74:**
Replace:
```typescript
  // If roles are not available in the session (common in next-auth default config),
  // allow access and let the backend enforce the permission check via the proxy.
  // This provides a graceful fallback — the backend always has the final say.
  const allowAccess = hasAdminRole || allRoles.length === 0;
```
With:
```typescript
  // Only grant access when an admin role is explicitly present.
  // Backend RBAC (RBAC gate 2) is the final enforcement gate; this is defense-in-depth.
  const allowAccess = hasAdminRole;
```
Rationale: Both Keycloak sessions and local-auth sessions populate realmRoles from the JWT (auth.ts:112, auth.ts:135 propagate realm_roles from the token). A session with no roles means the user has no admin role — the fallback allowing zero-roles access was overly permissive. Backend RBAC remains the authoritative gate.

**backend/tests/test_skill_export.py — lines 264-268:**
The issue: `_auth_override()` is an async function. Calling it without `await` creates an unawaited coroutine object that is passed as `mock_auth.return_value`. When FastAPI awaits the dependency, it gets the coroutine (already created, not a callable), causing RuntimeWarning.

Fix: Remove the `_auth_override` async wrapper entirely. Set `mock_auth` as an `AsyncMock` returning `mock_user` directly. Since `_require_registry_manager` is an `async def` FastAPI dependency, the mock must be an `AsyncMock`.

Replace:
```python
        async def _auth_override():
            return mock_user

        mock_get_db.side_effect = _get_db_override
        mock_auth.return_value = _auth_override()
```
With:
```python
        mock_get_db.side_effect = _get_db_override
        mock_auth = AsyncMock(return_value=mock_user)
```
Note: `mock_auth` is a local variable reassignment — the `@patch` decorator's injected argument is shadowed by this assignment. This is intentional: the `@patch("api.routes.admin_skills._require_registry_manager")` argument is no longer needed after the reassignment but causes no harm. Alternatively, apply `app.dependency_overrides` pattern, but the shadow-and-replace approach is minimal and correct for this test structure.

Simpler alternative that avoids shadowing: change the test method signature to not receive mock_auth, and add `app.dependency_overrides[_require_registry_manager] = lambda: mock_user` inside the test body. However, the shadow approach is the minimal change — use it.

Actually, use the cleanest fix: convert `mock_auth` (the injected patch parameter) to an `AsyncMock` in-place using `mock_auth.return_value = mock_user` combined with making it awaitable. Since `@patch` injects a `MagicMock`, replace with:

```python
        mock_get_db.side_effect = _get_db_override
        mock_auth.return_value = mock_user  # _require_registry_manager returns UserContext directly
```

Then delete the `async def _auth_override()` function. The `_require_registry_manager` dependency is declared as `async def` returning `UserContext` — when patched with `@patch`, MagicMock's `return_value` is what AsyncMock wraps. But `MagicMock` is not awaitable by default.

Correct minimal fix:
1. Change the test to use `AsyncMock` for `mock_auth` at the parameter level, OR
2. Inside test body: `mock_auth.side_effect = AsyncMock(return_value=mock_user)`.

Use option 2 (minimal change):
```python
        async def _get_db_override():
            yield mock_session

        mock_get_db.side_effect = _get_db_override
        mock_auth.side_effect = AsyncMock(return_value=mock_user)
```
Remove the `async def _auth_override()` block entirely.
  </action>
  <verify>
    <automated>cd /home/tungmv/Projects/hox-agentos/backend && PYTHONPATH=. .venv/bin/pytest tests/test_skill_export.py -v -W error::RuntimeWarning 2>&1 | tail -20</automated>
  </verify>
  <done>
    - test_skill_export.py runs with -W error::RuntimeWarning and no warnings are raised (all tests pass or skip cleanly)
    - admin/layout.tsx line 74: allowAccess = hasAdminRole (no allRoles.length === 0 fallback)
    - Frontend TypeScript build passes: cd /home/tungmv/Projects/hox-agentos/frontend && pnpm exec tsc --noEmit exits 0
    - Backend full suite still passes: PYTHONPATH=. .venv/bin/pytest tests/ -q shows 718+ passed
  </done>
</task>

</tasks>

<verification>
After both tasks complete:

```bash
# 1. Confirm no dead-code TODOs remain
cd /home/tungmv/Projects/hox-agentos/backend
grep -rn "TODO: verify dead" agents/master_agent.py core/prompts.py
# Expected: no output

# 2. Confirm stale intent_classifier reference gone from prompts.py docstring
grep "intent_classifier" core/prompts.py
# Expected: no output

# 3. Backend test suite — no regressions, no RuntimeWarning from skill export
PYTHONPATH=. .venv/bin/pytest tests/ -q
# Expected: 718+ passed, 0 failed (1 skipped is ok)

# 4. Frontend TypeScript check
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
# Expected: exit 0, no errors

# 5. Confirm admin layout change
grep "allRoles.length" /home/tungmv/Projects/hox-agentos/frontend/src/app/admin/layout.tsx
# Expected: no output (fallback removed)
```
</verification>

<success_criteria>
- 5 tech debt items closed (item 4 intentionally skipped — informational only)
- Zero "TODO: verify dead" comments remain in master_agent.py and api-client.ts
- prompts.py module docstring does not reference intent_classifier.md
- admin/layout.tsx: allowAccess = hasAdminRole (no zero-roles bypass)
- test_skill_export.py: no RuntimeWarning about unawaited coroutine
- Backend: 718+ tests pass, 0 regressions
- Frontend: TypeScript strict mode build passes
</success_criteria>

<output>
After completion, create `.planning/quick/3-fix-all-tech-debt-from-v1-2-audit/3-SUMMARY.md` with:
- What was changed in each of the 5 files
- Test results confirming no regressions
- Confirmation that item 4 (sub-agent .md files) was intentionally skipped
</output>
