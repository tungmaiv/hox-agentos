# Phase 13: Local Auth — Design

**Date:** 2026-03-03
**Phase:** 13 of 14 (v1.2 Developer Experience)
**Requirements:** AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05

## Goal

Admins can manage local users and groups entirely within AgentOS, and employees can sign in with a local username/password as an alternative to Keycloak SSO — with identical RBAC and Tool ACL behavior for both auth paths.

## Key Design Decisions

| Decision | Choice | Alternative Considered |
|----------|--------|----------------------|
| User storage | PostgreSQL only (local_users table) | Keycloak Admin API — rejected: couples every CRUD op to Keycloak availability |
| JWT signing | HS256 with LOCAL_JWT_SECRET | RS256 with local keypair — rejected: HS256 simpler for single-service issuer |
| Token detection | Issuer claim dispatch (iss: blitz-local vs Keycloak issuer URL) | Try/catch fallback — rejected: slower (two decode attempts per local request) |
| Role model | Groups carry roles (User → Group → Roles) + direct user role overrides | Direct user→role only — rejected: inconsistent with Keycloak's group model |
| Login UI | Split buttons on /login (SSO button + credentials form) | Separate /login/local page — rejected: extra navigation step |
| Admin UI | New "Users" tab in /admin tabbed interface | Separate /admin/users and /admin/groups pages — rejected: breaks existing tab pattern |

## Data Model

### New Tables (Alembic Migration 017)

```sql
-- Local user accounts (parallel to Keycloak users)
CREATE TABLE local_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,  -- bcrypt via passlib
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Local groups (analogous to Keycloak groups)
CREATE TABLE local_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(64) UNIQUE NOT NULL,
    description TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- User ↔ Group membership (M2M)
CREATE TABLE local_user_groups (
    user_id UUID REFERENCES local_users(id) ON DELETE CASCADE,
    group_id UUID REFERENCES local_groups(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, group_id)
);

-- Group → Role assignments (M2M)
CREATE TABLE local_group_roles (
    group_id UUID REFERENCES local_groups(id) ON DELETE CASCADE,
    role VARCHAR(64) NOT NULL,
    PRIMARY KEY (group_id, role)
);

-- Direct user → Role overrides (optional, bypasses groups)
CREATE TABLE local_user_roles (
    user_id UUID REFERENCES local_users(id) ON DELETE CASCADE,
    role VARCHAR(64) NOT NULL,
    PRIMARY KEY (user_id, role)
);
```

No RLS on these tables — they are admin-only, not user-scoped data.

### Role Resolution

A local user's effective roles = union of:
1. All roles from all groups the user belongs to (via local_group_roles)
2. All direct roles on the user (via local_user_roles)

This mirrors Keycloak's realm_roles claim behavior.

## JWT Dual-Issuer Authentication

### New Environment Variable

`LOCAL_JWT_SECRET` — minimum 32-character random string, added to `backend/.env`.
`LOCAL_JWT_EXPIRES_HOURS` — optional, defaults to 8 (one workday).

### Token Flow (Local Login)

```
Frontend                  Backend                    PostgreSQL
   |                         |                          |
   |-- POST /auth/local/token -->                       |
   |   {username, password}  |                          |
   |                         |-- SELECT local_users --> |
   |                         |<-- user row ------------ |
   |                         |                          |
   |                         |  bcrypt.verify(password) |
   |                         |  compute roles (groups ∪ direct)
   |                         |  sign HS256 JWT          |
   |                         |                          |
   |<-- {access_token} ------|                          |
```

### Local JWT Claims (mirrors Keycloak exactly)

```json
{
  "sub": "a1b2c3d4-...",
  "iss": "blitz-local",
  "exp": 1741100000,
  "iat": 1741071200,
  "email": "alice@blitz.local",
  "preferred_username": "alice",
  "realm_roles": ["employee", "it-admin"]
}
```

### validate_token() Refactor

```python
async def validate_token(token: str) -> UserContext:
    # Step 1: Peek at issuer WITHOUT signature verification
    unverified = jose_jwt.get_unverified_claims(token)
    issuer = unverified.get("iss", "")

    # Step 2: Route to appropriate validator
    if issuer == settings.keycloak_issuer:
        return await _validate_keycloak_token(token)   # existing RS256 + JWKS
    elif issuer == "blitz-local":
        return _validate_local_token(token)            # new HS256 + LOCAL_JWT_SECRET
    else:
        raise HTTPException(401, "Unknown token issuer")
```

The existing `validate_token()` body becomes `_validate_keycloak_token()` with zero behavior change. `_validate_local_token()` does `jose_jwt.decode(token, settings.local_jwt_secret, algorithms=["HS256"], issuer="blitz-local")`.

## Admin CRUD API

New router: `backend/api/routes/admin_local_users.py`

All endpoints require `registry:manage` RBAC permission (same gate as other admin routes).

### User Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /admin/local/users | Create local user |
| GET | /admin/local/users | List users (paginated) |
| GET | /admin/local/users/{id} | Get user detail |
| PUT | /admin/local/users/{id} | Update user (password optional) |
| DELETE | /admin/local/users/{id} | Delete user |
| POST | /admin/local/users/{id}/groups | Assign group(s) |
| DELETE | /admin/local/users/{id}/groups/{group_id} | Remove from group |
| POST | /admin/local/users/{id}/roles | Add direct role(s) |
| DELETE | /admin/local/users/{id}/roles/{role} | Remove direct role |

### Group Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /admin/local/groups | Create group |
| GET | /admin/local/groups | List groups |
| PUT | /admin/local/groups/{id} | Update group (name, desc, roles) |
| DELETE | /admin/local/groups/{id} | Delete group |

### Response Schema

User responses never include `password_hash`. User list includes computed `roles` (resolved from groups + direct).

## Frontend Changes

### NextAuth Credentials Provider (auth.ts)

```ts
Credentials({
  credentials: {
    username: { label: "Username", type: "text" },
    password: { label: "Password", type: "password" },
  },
  async authorize(credentials) {
    const res = await fetch(`${BACKEND_URL}/auth/local/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credentials),
    });
    if (!res.ok) return null;
    const { access_token } = await res.json();
    const payload = decodeJwt(access_token);
    return {
      id: payload.sub,
      name: payload.preferred_username,
      email: payload.email,
      accessToken: access_token,
    };
  },
})
```

The `jwt()` callback updated: when `user?.accessToken` is present (Credentials path), store as `token.accessToken`. No refresh token for local auth — user re-authenticates after expiry.

### Login Page (/login)

```
┌─────────────────────────────────┐
│                                 │
│   [ Sign in with Keycloak SSO ] │
│                                 │
│   ──────── or ────────          │
│                                 │
│   Username: ________________    │
│   Password: ________________    │
│   [ Sign in ]                   │
│                                 │
└─────────────────────────────────┘
```

Keycloak button calls `signIn("keycloak")`. Credentials form calls `signIn("credentials", { username, password })`.

### /admin Users Tab

New tab added to `/admin/layout.tsx` tab bar.

**Local Users sub-section:**
- Table columns: Username, Email, Groups, Roles (resolved), Status, Actions
- Create User dialog: username, email, password, group assignments (multiselect), direct roles (multiselect)
- Edit User dialog: all fields editable, password change optional
- Delete with confirmation

**Groups sub-section:**
- Table columns: Name, Description, Roles, Member Count, Actions
- Create Group dialog: name, description, roles (multiselect from known roles)
- Edit/Delete with confirmation

## Plan Breakdown

### Plan 13-01: Backend Local Auth (DB + JWT + API)
- SQLAlchemy ORM models for 5 new tables
- Alembic migration 017
- `passlib[bcrypt]` dependency
- `LOCAL_JWT_SECRET` + `LOCAL_JWT_EXPIRES_HOURS` in core/config.py
- `POST /auth/local/token` endpoint (no auth required — it IS the auth)
- Refactor `validate_token()` into dual-issuer dispatcher
- Admin CRUD routes for users and groups
- Pydantic schemas for all request/response bodies
- Tests: local JWT issue + validate, Keycloak path unchanged, CRUD ops, RBAC gate, role resolution

### Plan 13-02: Frontend Local Auth (Login + Admin UI)
- NextAuth Credentials provider in auth.ts
- jwt() callback update for dual-provider
- /login page redesign (SSO + credentials)
- /admin Users tab (users table + groups table + CRUD dialogs)
- TypeScript strict compliance
- Admin proxy routes for local user/group API calls

## Security Considerations

- Passwords stored as bcrypt hashes — never plaintext, never logged
- LOCAL_JWT_SECRET must be cryptographically random (min 32 chars)
- Local JWTs carry the same claim structure as Keycloak → RBAC and Tool ACL work identically
- No self-registration — only admins can create local accounts (AUTH-01)
- Account deactivation (is_active=false) immediately blocks login
- Rate limiting on /auth/local/token endpoint (optional, can add brute-force protection later)

## Success Criteria Mapping

| SC | Requirement | How Satisfied |
|----|-------------|---------------|
| 1 | AUTH-01: Admin CRUD local users | Admin CRUD API + Users tab in /admin |
| 2 | AUTH-02: Admin manages groups with roles | Groups CRUD + group_roles table |
| 3 | AUTH-04: Local login on login page | Credentials form on /login + POST /auth/local/token |
| 4 | AUTH-05: Same JWT claims → same RBAC | realm_roles in local JWT, iss-dispatch in validate_token() |
| 5 | AUTH-03 + AUTH-05: Local admin works | it-admin role in local JWT → /admin access identical |
