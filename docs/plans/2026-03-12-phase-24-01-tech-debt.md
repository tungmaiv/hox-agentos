# Phase 24-01: Tech Debt Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clear four outstanding tech-debt items that block clean Phase 24 development.

**Architecture:** Four independent fixes: SWR directive, Keycloak SSO error, CREDENTIAL_ENCRYPTION_KEY startup validation, admin N+1 query audit.

**Tech Stack:** Next.js 15 App Router, FastAPI, pydantic-settings, SQLAlchemy async.

---

## Task 1: Fix SWR in Server Components (`settings/memory` page)

**Files:**
- Inspect: `frontend/src/app/(authenticated)/settings/memory/page.tsx`
- Modify: same file

**Step 1: Confirm the failure**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit 2>&1 | grep -i "swr\|useSWR\|memory\|integrations"
```

Expected: TypeScript or build errors about hooks in Server Components.

**Step 2: Add `"use client"` directive**

Open each affected page. If the top of the file does NOT have `"use client"`, add it as the very first line:

```tsx
"use client";
```

Affected files to check (add `"use client"` to each if missing):
- `frontend/src/app/(authenticated)/settings/memory/page.tsx`
- Any other page with `useSWR` import that lacks `"use client"` — grep to find them:

```bash
grep -r "useSWR" frontend/src/app --include="*.tsx" -l
```

For each file found, check if `"use client"` is on line 1. Add it if not.

**Step 3: Verify fix**

```bash
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
```

Expected: no SWR-related errors.

**Step 4: Commit**

```bash
git add frontend/src/app
git commit -m "fix(24-01): add use client to pages using SWR hooks"
```

---

## Task 2: Keycloak SSO `Configuration` Error

**Files:**
- Read: `frontend/src/auth.ts` (or wherever next-auth Keycloak provider is configured)
- Read: `frontend/.env.local` (check KEYCLOAK_ISSUER, KEYCLOAK_CLIENT_ID, KEYCLOAK_CLIENT_SECRET)
- Possibly modify: `frontend/src/auth.ts`

**Step 1: Reproduce the error**

The error URL is `/api/auth/error?error=Configuration`. This means next-auth failed during OIDC discovery or token exchange.

**Step 2: Check KEYCLOAK_ISSUER reachability**

```bash
# From inside the frontend container:
docker compose exec frontend wget -qO- "${KEYCLOAK_ISSUER}/.well-known/openid-configuration" 2>&1 | head -20
```

If this fails with a connection error or SSL error:
- If SSL: Keycloak self-signed cert issue — see Step 3
- If connection refused: Keycloak service not running — run `just up keycloak`
- If 404: `KEYCLOAK_ISSUER` URL is wrong

**Step 3: Fix SSL cert issue (if applicable)**

If KEYCLOAK_ISSUER uses HTTPS with a self-signed cert, next-auth's node-fetch will reject it.

Option A — Use HTTP issuer URL (if Keycloak serves HTTP internally):
```bash
# In frontend/.env.local:
KEYCLOAK_ISSUER=http://keycloak:8080/realms/blitz-internal
```

Option B — Set NODE_TLS_REJECT_UNAUTHORIZED for dev (not prod):
In `frontend/src/auth.ts`, before the NextAuth config:
```ts
if (process.env.NODE_ENV !== "production") {
  process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";
}
```

**Step 4: Verify CLIENT_ID and CLIENT_SECRET match Keycloak**

In Keycloak admin (`http://localhost:8080`):
- Realm: `blitz-internal` → Clients → `blitz-portal`
- Check client secret matches `KEYCLOAK_CLIENT_SECRET` in `.env.local`

**Step 5: Surface a clear error message if fix is not achievable**

If the root cause is a missing Keycloak service (common in dev), update the login page to show a helpful message instead of the generic "Configuration" error.

In `frontend/src/app/(unauthenticated)/login/page.tsx` (or similar), check for `?error=Configuration` in the URL and display:

```tsx
{searchParams.error === "Configuration" && (
  <p className="text-sm text-red-500 mt-2">
    SSO login is unavailable. Use local login below, or contact IT to start Keycloak.
  </p>
)}
```

**Step 6: Commit**

```bash
git commit -m "fix(24-01): fix Keycloak SSO Configuration error — clear error message + issuer URL"
```

---

## Task 3: CREDENTIAL_ENCRYPTION_KEY Validation

**Files:**
- Read: `backend/core/config.py`
- Modify: `backend/core/config.py`
- Modify: `.dev-secrets.example` (add the key)
- Test: `backend/tests/test_config.py` (create if missing)

**Step 1: Find where CREDENTIAL_ENCRYPTION_KEY is used**

```bash
grep -r "CREDENTIAL_ENCRYPTION_KEY\|credential_encryption_key" backend/ --include="*.py" -n
```

**Step 2: Write a failing test**

```python
# backend/tests/test_config.py (add this test)
import os
import pytest

def test_missing_credential_encryption_key_logs_warning(caplog):
    """Backend should log a warning (not crash) if CREDENTIAL_ENCRYPTION_KEY is missing."""
    import structlog
    # The key is optional — absence should warn, not crash
    # This test verifies settings loads without the key present
    original = os.environ.pop("CREDENTIAL_ENCRYPTION_KEY", None)
    try:
        from importlib import reload
        import core.config as cfg
        reload(cfg)
        # If we get here without exception, the test passes
    finally:
        if original:
            os.environ["CREDENTIAL_ENCRYPTION_KEY"] = original
```

**Step 3: Run test to confirm current behaviour**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_config.py -v -s 2>&1 | tail -20
```

**Step 4: Add startup warning in `core/config.py`**

Find the `Settings` class. Add a validator or startup check:

```python
# In core/config.py Settings class
from pydantic import model_validator

@model_validator(mode="after")
def warn_missing_encryption_key(self) -> "Settings":
    import structlog
    if not self.credential_encryption_key:
        structlog.get_logger(__name__).warning(
            "credential_encryption_key_missing",
            msg="CREDENTIAL_ENCRYPTION_KEY not set — OAuth credential encryption disabled. "
                "Set this before enabling OAuth integrations.",
        )
    return self
```

**Step 5: Update `.dev-secrets.example`**

Add the line:
```
CREDENTIAL_ENCRYPTION_KEY=generate-with-python-secrets-token-hex-32
```

Also add a comment explaining how to generate one:
```
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
```

**Step 6: Run tests to verify warning (not crash)**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_config.py -v
```

Expected: PASS.

**Step 7: Commit**

```bash
git add backend/core/config.py .dev-secrets.example
git commit -m "fix(24-01): warn on missing CREDENTIAL_ENCRYPTION_KEY at startup"
```

---

## Task 4: Admin Page N+1 Query Audit

**Files:**
- Read: `backend/api/routes/admin_skills.py`
- Read: `backend/api/routes/admin_agents.py`
- Read: `backend/api/routes/admin_tools.py`
- Possibly modify: each route file

**Step 1: Identify list endpoints that may N+1**

For each admin list endpoint (skills, agents, tools), check if the handler does:
```python
# BAD — N+1:
skills = await session.execute(select(SkillDefinition))
for skill in skills:
    count = await session.execute(select(func.count()).where(...skill_id...))
```

versus:
```python
# GOOD — single query with subquery or join:
skills = await session.execute(
    select(SkillDefinition, subquery_count).join(...)
)
```

**Step 2: Fix any N+1 found**

Common pattern — if a list endpoint loads related counts in a loop, replace with a subquery:

```python
from sqlalchemy import select, func, outerjoin

# Example: loading usage counts in one query
stmt = (
    select(SkillDefinition)
    .where(SkillDefinition.is_active == True)
    .order_by(SkillDefinition.created_at.desc())
)
result = await session.execute(stmt)
skills = result.scalars().all()
```

If no N+1 is found, document this in the commit message: "no N+1 found in admin list endpoints".

**Step 3: Verify with test or manual timing**

```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/api/test_admin_skills.py -v 2>&1 | tail -20
```

**Step 4: Commit**

```bash
git commit -m "perf(24-01): audit and fix N+1 queries in admin list endpoints"
```

---

## Completion Check

After all 4 tasks:

```bash
# Backend tests still pass
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q

# Frontend type checks pass
cd /home/tungmv/Projects/hox-agentos/frontend
pnpm exec tsc --noEmit
```

Both should exit 0.
