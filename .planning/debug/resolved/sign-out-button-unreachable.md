---
status: resolved
trigger: "Sign Out button not reachable in UI"
created: 2026-03-05T00:00:00Z
updated: 2026-03-05T00:00:00Z
---

## Current Focus

hypothesis: AuthHeader component (which wraps SignOutButton) is defined but never imported into any page or layout. SignOutButton is also never imported standalone. The useAuth hook (which exposes logout()) is never consumed by any component.
test: grep for AuthHeader, SignOutButton, and useAuth imports across all pages/layouts
expecting: zero imports outside their definition files
next_action: report root cause

## Symptoms

expected: Sign Out button should be accessible from the main authenticated UI
actual: No Sign Out button visible anywhere after logging in
errors: none (no runtime error -- component simply never rendered)
reproduction: Log in, navigate to /chat or /settings -- no sign out option anywhere
started: always broken (component was created but never wired in)

## Eliminated

(none -- root cause found on first investigation pass)

## Evidence

- timestamp: 2026-03-05T00:01:00Z
  checked: grep for "AuthHeader" across frontend/
  found: only match is its own definition file (frontend/src/components/auth-header.tsx)
  implication: AuthHeader is never imported by any page or layout

- timestamp: 2026-03-05T00:02:00Z
  checked: grep for "SignOutButton" and "sign-out-button" across frontend/src/
  found: only matches are sign-out-button.tsx (definition) and auth-header.tsx (which imports it but is itself unused)
  implication: SignOutButton is not imported standalone anywhere either

- timestamp: 2026-03-05T00:03:00Z
  checked: grep for "useAuth" across frontend/src/
  found: only match is its own definition file (frontend/src/hooks/use-auth.ts)
  implication: the useAuth hook (which exposes logout()) is never consumed by any component

- timestamp: 2026-03-05T00:04:00Z
  checked: conversation-sidebar.tsx (main sidebar in chat page)
  found: footer section (lines 168-177) has a Settings link but NO sign-out button. Header section (lines 74-87) shows userEmail and "New Conversation" button but NO sign-out.
  implication: the sidebar is the natural place for sign-out but it was never added

- timestamp: 2026-03-05T00:05:00Z
  checked: settings/page.tsx
  found: no sign-out option anywhere on the settings page either
  implication: even navigating to settings provides no way to sign out

- timestamp: 2026-03-05T00:06:00Z
  checked: app/layout.tsx (root layout)
  found: contains SessionProvider and AuthErrorToasts -- no AuthHeader
  implication: root layout does not include a global auth header

- timestamp: 2026-03-05T00:07:00Z
  checked: app/chat/page.tsx
  found: renders only ChatLayout -- no AuthHeader
  implication: chat page does not include auth header

## Resolution

root_cause: Three sign-out mechanisms exist but none are wired into the UI:
  1. AuthHeader component (frontend/src/components/auth-header.tsx) -- defined but never imported by any page or layout
  2. SignOutButton component (frontend/src/components/sign-out-button.tsx) -- only imported by AuthHeader (which is unused)
  3. useAuth hook (frontend/src/hooks/use-auth.ts) -- exposes logout() but is never consumed by any component

The conversation sidebar (frontend/src/components/chat/conversation-sidebar.tsx) is the most natural placement -- it already shows userEmail and has a footer with a Settings link, but no sign-out option.

fix: (not applied -- diagnosis only)
verification: (not applied -- diagnosis only)
files_changed: []
