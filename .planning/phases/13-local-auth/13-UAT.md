---
status: complete
phase: 13-local-auth
source: 13-01-SUMMARY.md, 13-02-SUMMARY.md
started: 2026-03-04T00:00:00Z
updated: 2026-03-04T00:30:00Z
---

## Current Test

## Current Test

[testing complete]

## Tests

### 1. Login page layout
expected: Navigate to /login. Page shows SSO button + divider + username/password credentials form.
result: pass

### 2. Local user login
expected: Enter a valid local username and password in the credentials form, submit. Redirects to /chat (or home). No error shown.
result: pass

### 3. Wrong credentials error
expected: Enter an invalid username or wrong password, submit. An inline error message appears (e.g. "Invalid credentials" or similar). No redirect.
result: pass

### 4. Session expired notice
expected: Navigate to /login?error=SessionExpired. A notice/banner appears saying something like "Your session has expired, please sign in again." The form is still usable.
result: pass

### 5. Admin Users tab visible
expected: Log in as an admin, navigate to /admin. The tab bar includes a "Users" tab (in addition to existing tabs like Config, MCP Servers, etc.).
result: pass

### 6. Create local user with password toast
expected: On /admin/users, click "Create User". Fill in username, email, password, optionally assign groups/roles. Submit. The new user appears in the Local Users table. A toast/notification appears with the password (copyable). Dismissing the toast = gone forever (no way to retrieve it again).
result: pass

### 7. Edit local user
expected: Click the edit action on a local user. A dialog opens pre-filled with username and email. Update one field, save. The table row reflects the change.
result: pass

### 8. Delete local user
expected: Click delete on a local user. A confirmation dialog appears showing the username. Confirm. The user is removed from the table.
result: pass

### 9. Create group
expected: On /admin/users, in the Groups section, click "Create Group". Fill in name, description, and optionally assign roles. Submit. The new group appears in the Groups table.
result: pass

### 10. Edit group
expected: Click edit on a group. Dialog opens with current name/description/roles pre-filled. Make a change, save. Table row updates.
result: pass

### 11. Delete group
expected: Click delete on a group. Confirmation dialog shows the group name. Confirm. Group removed from table.
result: pass

### 12. Local JWT works for API calls
expected: After logging in with local credentials, the chat page loads and the agent responds normally (i.e., the local JWT is accepted by the backend for API calls).
result: pass

## Summary

total: 12
passed: 12
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
