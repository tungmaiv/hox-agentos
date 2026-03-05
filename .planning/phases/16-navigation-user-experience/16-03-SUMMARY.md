---
phase: 16-navigation-user-experience
plan: "03"
subsystem: ui-profile
tags: [next-js, profile-page, user-preferences, agent-prompt, settings, fastapi]
dependency_graph:
  requires:
    - 16-01 (user-preferences-api: get_user_preference_values helper, GET/PUT /api/users/me/preferences)
    - 16-02 ((authenticated) route group with NavRail, /profile placeholder ready)
  provides:
    - full-profile-page
    - change-password-backend-endpoint
    - preferences-frontend-proxy
    - agent-preference-injection
  affects:
    - master_agent.py (system prompt now includes thinking_mode and response_style directives)
    - settings page (custom instructions and chat preferences removed)
tech_stack:
  added: []
  patterns:
    - Next.js Server Component page shell with Client Component cards
    - Auto-save on toggle/radio with optimistic UI and brief Saved indicator
    - Inline expandable form (not modal) for password change
    - useEffect+setInterval for live session expiry countdown
key_files:
  created:
    - frontend/src/app/(authenticated)/profile/page.tsx
    - frontend/src/components/profile/account-info-card.tsx
    - frontend/src/components/profile/password-change-card.tsx
    - frontend/src/components/profile/custom-instructions-card.tsx
    - frontend/src/components/profile/llm-preferences-card.tsx
    - frontend/src/app/api/users/me/preferences/route.ts
    - frontend/src/app/api/auth/local/change-password/route.ts
    - backend/api/routes/auth_local_password.py
  modified:
    - frontend/src/app/(authenticated)/settings/page.tsx
    - backend/agents/master_agent.py
    - backend/main.py
key_decisions:
  - "Backend change-password endpoint added (auth_local_password.py) — was missing, required for PasswordChangeCard (Rule 2 auto-fix)"
  - "user_prefs loaded in same async_session block as custom_instructions — no extra DB round-trip"
  - "concise response style gets no extra directive — base master_agent prompt is already concise"
  - "Session expiresAt from JWT token (expiresAt field on next-auth JWT type) used for countdown"
  - "PasswordChangeCard returns null when authProvider !== credentials — SSO users never see it"
metrics:
  duration_seconds: 271
  completed_date: "2026-03-05"
  tasks_completed: 2
  files_created: 8
  files_modified: 3
  tests_added: 0
  test_suite_before: 725
  test_suite_after: 725
---

# Phase 16 Plan 03: Profile Page and Preferences Injection Summary

**One-liner:** Full profile page with 4 card sections (account info, custom instructions, LLM prefs, password change), preference directives injected into master agent system prompt, and settings page slimmed to Memory + Channel Linking only.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Build profile page with card sections | fd8e8cb | profile/page.tsx, 4 card components, 2 API proxy routes, backend change-password endpoint |
| 2 | Update settings page and inject preferences into agent prompt | 367d52f | settings/page.tsx, master_agent.py |

## What Was Built

### Profile Page (`frontend/src/app/(authenticated)/profile/page.tsx`)
- Server Component page shell; imports 4 Client Component cards
- Admin link shown on mobile (`md:hidden`) for admin/developer/it-admin roles
- SignOutButton at the bottom

### AccountInfoCard (`components/profile/account-info-card.tsx`)
- Displays name, email, auth provider badge (SSO purple / Local blue), roles as gray badges
- Session expiry countdown via `useEffect` + `setInterval` every 60s
- Reads `expiresAt` from JWT token via `useSession()` → session cast to Record

### PasswordChangeCard (`components/profile/password-change-card.tsx`)
- Returns `null` for SSO users (`authProvider !== "credentials"`)
- Inline expandable form (not modal): current + new + confirm password fields
- Validates new === confirm before sending; backend enforces complexity (8 chars, upper/lower/digit)
- Success: green message, form collapses. Error: inline red text

### CustomInstructionsCard (`components/profile/custom-instructions-card.tsx`)
- Fetches from `/api/user/instructions/` on mount; saves via PUT with manual Save button
- Character count + "Saved ✓" indicator — same UX as old settings page but in card container

### LLMPreferencesCard (`components/profile/llm-preferences-card.tsx`)
- Fetches from `/api/users/me/preferences` on mount
- Thinking mode: toggle switch with `role="switch"` aria attribute
- Response style: radio group (concise/detailed/conversational) with description
- Auto-save on change: PUT with partial body; brief "Saved ✓" fades after 1.5s (no toast)

### Preferences Proxy Route (`frontend/src/app/api/users/me/preferences/route.ts`)
- GET + PUT handlers forwarding to backend `GET/PUT /api/users/me/preferences/`
- Injects server-side Bearer token from `auth()` session

### Change-Password Proxy Route (`frontend/src/app/api/auth/local/change-password/route.ts`)
- POST handler forwarding to backend `POST /api/auth/local/change-password`
- Injects server-side Bearer token from `auth()` session

### Backend Change-Password Endpoint (`backend/api/routes/auth_local_password.py`)
- `POST /api/auth/local/change-password` — JWT protected via `get_current_user` dep
- Looks up `LocalUser` by `user_id` from JWT; returns 400 if not a local user
- Verifies current password via `verify_password()` before accepting new one
- `hash_password()` enforces complexity (raises ValueError → 422)
- Registered in `main.py` as `auth_local_password_router`

### Settings Page (`frontend/src/app/(authenticated)/settings/page.tsx`)
- Removed: Custom Instructions textarea, Chat Preferences card link, Back to chat link
- Kept: Memory card link, Channel Linking card link
- Updated subtitle: "Application configuration"

### Agent Preference Injection (`backend/agents/master_agent.py`)
- Imports `get_user_preference_values` from `api.routes.user_preferences`
- Loads `user_prefs` in the same `async_session` block as `custom_instructions` — no extra DB session
- Appends `thinking_mode` directive: show `<thinking>` block before answering
- Appends `detailed` response style directive: thorough explanations with headings/lists
- Appends `conversational` response style directive: friendly, engaging, follow-up questions
- `concise` style (default) — no extra directive (base prompt already concise)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Added backend change-password endpoint**
- **Found during:** Task 1
- **Issue:** `backend/api/routes/auth_local.py` had no change-password endpoint. Plan context referenced `POST /api/auth/local/change-password` as "already existing" but it was absent.
- **Fix:** Created `backend/api/routes/auth_local_password.py` with full bcrypt verification and complexity validation. Registered in `main.py`.
- **Files modified:** `backend/api/routes/auth_local_password.py` (new), `backend/main.py`
- **Commit:** fd8e8cb (included in Task 1 commit)

## Verification Results

- `pnpm exec tsc --noEmit`: 0 errors
- `pytest tests/ -q`: 725 passed, 1 skipped (same as baseline — no regressions)
- Profile page at /profile: 4 card sections, SignOut button, mobile admin link for admins
- Settings page: only Memory and Channel Linking cards
- master_agent.py: loads thinking_mode and response_style in same DB session as custom_instructions

## Self-Check: PASSED

Files created:
- FOUND: frontend/src/app/(authenticated)/profile/page.tsx
- FOUND: frontend/src/components/profile/account-info-card.tsx
- FOUND: frontend/src/components/profile/password-change-card.tsx
- FOUND: frontend/src/components/profile/custom-instructions-card.tsx
- FOUND: frontend/src/components/profile/llm-preferences-card.tsx
- FOUND: frontend/src/app/api/users/me/preferences/route.ts
- FOUND: frontend/src/app/api/auth/local/change-password/route.ts
- FOUND: backend/api/routes/auth_local_password.py

Commits:
- FOUND: fd8e8cb (feat(16-03): build profile page with 4 card sections and API routes)
- FOUND: 367d52f (feat(16-03): update settings page and inject preferences into agent prompt)
