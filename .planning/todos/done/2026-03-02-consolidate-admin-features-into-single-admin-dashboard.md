---
created: 2026-03-02T03:22:06.112Z
title: Consolidate admin features into single admin dashboard
area: ui
files: []
---

## Problem

There are currently two separate admin screens:
- `http://localhost:3000/settings` — contains some admin features
- `http://localhost:3000/admin` — the primary admin area

Admin functionality is split across both routes, creating a fragmented UX. All admin features from `/settings` need to be migrated to `/admin` so there is a single unified admin desk.

## Solution

1. Audit what admin-specific features/sections exist in `frontend/src/app/settings/`
2. Move or re-implement those admin features into `frontend/src/app/admin/`
3. Update `/settings` to only contain non-admin (per-user) settings
4. Add redirects or remove the admin portions from `/settings` to avoid duplication
5. Ensure `/admin` is access-controlled (admin role required)
