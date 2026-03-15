---
created: 2026-03-15T06:51:58.504Z
title: "Implement Advanced User & Group Management (Topic #12)"
area: auth
priority: high
target: v1.5-enhancement
effort: 1 phase
existing_code: 30%
depends_on: []
design_doc: docs/enhancement/topics/12-advanced-user-group-management/00-specification.md
files:
  - backend/core/models/local_auth.py
  - backend/api/routes/admin_local_users.py
  - backend/alembic/versions/017_local_auth_tables.py
---

## Problem

Current permission model uses role indirection: `Group → Roles → Permissions`. The confirmed architecture decision is to replace this with direct permissions: `External IDP (Keycloak) → Global Groups → Local Groups → Permissions`. This is a **breaking change** but clean slate is possible since no production deployments exist.

## What Exists (30%)

- `local_users` table — username, email, password_hash, is_active
- `local_groups` table — name, description
- `local_user_groups` table — M2M user↔group
- `local_group_roles` table — roles attached to groups (to be replaced)
- `local_user_roles` table — direct role overrides
- Admin user management API at `/api/admin/local-users`
- Basic group management routes

## What's Needed (BREAKING CHANGE)

**New permission model (confirmed in ANALYSIS-REPORT.md Session 3):**
- **`global_groups` table** — read-only mirror of external IDP (Keycloak) groups
- **`group_permissions` table** — direct permission assignment (replaces role indirection)
- **`group_mappings` table** — mapping between Keycloak global groups and local groups
- **Remove `local_group_roles`** — eliminate role indirection table
- **External IDP sync** — Keycloak group synchronization mechanism
- **Permission source attribution** — indicate whether permission comes from group or direct assignment
- **Group detail pages** — frontend UI for group management beyond basic listing
- **Inline group editing** — edit user's group memberships from user detail page
- **Visual permission lists** — expanded view of what permissions a group grants

## Solution

Follow specification at `docs/enhancement/topics/12-advanced-user-group-management/00-specification.md`. Implement fresh without backward compatibility concerns (clean slate approved).
