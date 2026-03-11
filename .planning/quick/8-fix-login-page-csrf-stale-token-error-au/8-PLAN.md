---
quick: 8
slug: fix-login-page-csrf-stale-token-error-au
description: fix login page CSRF stale-token error: auto-reload instead of misleading invalid-password message
created: 2026-03-11
---

## Goal

When a user's next-auth CSRF token goes stale (e.g. after a frontend container restart or long idle), the login form returns `result.error = "MissingCSRF"` or another non-credential error. The current code maps ALL errors to "Invalid username or password" — confusing and misleading.

Fix: distinguish `"CredentialsSignin"` (bad password) from all other errors. Non-credential errors trigger `window.location.reload()` which fetches a fresh CSRF token automatically — user just sees the page reload and can log in immediately.

## Task 1: login/page.tsx — distinguish credential vs non-credential errors

**File:** `frontend/src/app/login/page.tsx`

**Change:** In `handleCredentialsSubmit`, replace the catch-all `result?.error` branch with:
- `result.error === "CredentialsSignin"` → show "Invalid username or password"
- anything else → `window.location.reload()` (gets fresh CSRF token)

**Done when:** TypeScript passes, `tsc --noEmit` exits 0.
