---
created: 2026-03-03T14:26:45.571Z
title: Add user profile and logout to UI with session expiration
area: ui
files:
  - frontend/src/components/
  - frontend/src/app/
  - backend/security/
  - backend/api/routes/auth.py
---

## Problem

Currently the UI lacks user profile management and session control features:

1. **No user profile display**: Users cannot see their profile information (name, email, roles) or access account settings from the UI
2. **No logout functionality**: There's no way to log out of the application, leaving sessions active indefinitely
3. **No session timeout**: Sessions don't expire automatically, creating security risks for shared or public computers
4. **No timeout configuration**: Users cannot customize their session timeout duration based on their security preferences

## Solution

### Frontend UI Changes

1. **User profile menu** in header/navbar:
   - Display current user name/email
   - Dropdown with: Profile, Settings, Logout options
   - Profile page showing user details from JWT claims

2. **Logout functionality**:
   - Clear local JWT token storage
   - Call backend logout endpoint (if Keycloak session exists, terminate it)
   - Redirect to login page

3. **Settings page** with session timeout configuration:
   - Session timeout duration selector (15min, 30min, 1hr, 4hr, 8hr, never)
   - Save preference to backend user settings
   - Default: 1 hour

4. **Session expiration handling**:
   - Client-side timer that tracks inactivity
   - Warning modal 5 minutes before expiration
   - Auto-logout when timeout reached
   - On activity, reset timer

### Backend Changes

1. **Logout endpoint** `POST /api/auth/logout`:
   - Clear server-side session if any
   - If Keycloak token exists, call Keycloak logout endpoint
   - Return success

2. **User settings endpoint** `GET/PUT /api/user/settings`:
   - Store session_timeout_preference (in minutes, 0 = never)
   - Return settings on login for client timer initialization

3. **Token refresh handling**:
   - Check if session timeout exceeded before refreshing
   - Deny refresh if timeout reached

### Security Considerations

- Session timeout should be enforced both client-side (UX) and server-side (security)
- Keycloak session termination requires admin API call with proper credentials
- Inactivity detection: mouse move, key press, scroll, touch events
