# Quick Task 8: Fix login page CSRF stale-token error

## One-liner
Login page now auto-reloads (getting a fresh CSRF token) instead of showing "Invalid username or password" when a stale CSRF token is the actual cause.

## What changed

**`frontend/src/app/login/page.tsx`** — `handleCredentialsSubmit`:
- `result.error === "CredentialsSignin"` → "Invalid username or password. Please try again." (unchanged for real bad passwords)
- any other error (e.g. `"MissingCSRF"`, `"Configuration"`) → `window.location.reload()` — page reloads silently with a fresh CSRF token; user can sign in immediately on the reloaded page

## Why this matters

Every frontend container restart (deploy, crash recovery, `just restart frontend`) invalidates all in-flight CSRF tokens. Users who had the login page open in their browser would see "Invalid username or password" when they hadn't done anything wrong. The auto-reload recovers transparently with no user confusion.

## Commits

- `fix(quick-8): auto-reload on stale CSRF token instead of misleading error`
