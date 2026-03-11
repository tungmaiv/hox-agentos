---
created: 2026-03-09T16:15:29.822Z
title: Update user and group management — allow edit user/group memberships
area: auth
files:
  - frontend/src/app/(authenticated)/admin/identity/page.tsx
  - backend/api/routes/admin_local_users.py
---

## Problem

The admin `/admin/identity` (Users tab) currently supports creating and deleting local users, but does not allow editing group membership after creation. Admins cannot:
- Move a user from one group to another
- Add a user to an additional group from the group detail view
- Remove a user from a group from the group detail view

This creates a management gap — the only way to change a user's group is to delete and recreate them.

Related to: `2026-03-02-add-local-user-and-group-management-with-dual-auth-keycloak-and-local.md` (initial setup todo — this extends it with edit operations).

## Solution

1. **User edit form** — add a "Groups" multi-select/picker on the user edit panel in `/admin/identity`
   - Lists all available groups
   - Shows current memberships
   - POST `/api/admin/local/users/{id}/groups` to add, DELETE `/api/admin/local/users/{id}/groups/{group_id}` to remove
2. **Group detail panel** — add "Members" section showing current users, with "Add user" dropdown and "Remove" button per member
   - Same backend endpoints (already exist per `admin_local_users.py` route headers)
3. Backend endpoints already exist (`POST /api/admin/local/users/{id}/groups` and `DELETE .../groups/{group_id}`) — this is purely a UI gap
