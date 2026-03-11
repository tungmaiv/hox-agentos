---
created: 2026-03-02T03:23:58.355Z
title: Add local user and group management with dual auth (Keycloak and local)
area: auth
files: []
---

## Problem

AgentOS currently only supports authentication via Keycloak (SSO). There is no local user/group management, meaning every user must exist in Keycloak. This creates a dependency on Keycloak being fully operational and makes it harder to onboard users who don't use SSO or for offline/air-gapped scenarios.

The goal is to support **dual authentication**:
1. Keycloak SSO (existing)
2. Local username/password accounts managed directly in AgentOS

## Solution

1. Add a `local_users` table in PostgreSQL to store local accounts (hashed passwords, roles, group memberships)
2. Add a `groups` table for local group management
3. Extend `backend/security/jwt.py` (or create a parallel auth path) to issue internal JWTs for local users
4. Add admin UI in `/admin` for:
   - Creating/editing/deleting local users
   - Assigning users to groups
   - Setting roles (admin, user, etc.)
5. Update login flow (frontend) to offer both "Sign in with Keycloak" and "Local login" options
6. Ensure RBAC and tool ACL work identically for both auth sources — local JWT must carry same claims structure as Keycloak JWT
7. Keep Keycloak as the primary/preferred auth; local auth is a fallback or parallel option
