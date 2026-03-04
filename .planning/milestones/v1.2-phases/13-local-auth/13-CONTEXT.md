# Phase 13: Local Auth - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Admins can manage local users and groups entirely within AgentOS, and employees can sign in with a local username/password as an alternative to Keycloak SSO — with identical RBAC and Tool ACL behavior for both auth paths. No self-registration, no identity linking, no session management UI.

</domain>

<decisions>
## Implementation Decisions

### Password policy & onboarding
- Admin sets the initial password during user creation — communicated to user out-of-band (verbally, chat, etc.)
- No forced password change on first login — user logs in directly with the password admin set
- After creating a user, show the password once in a copyable success toast (dismissed = gone forever)
- New local users are active by default (is_active=true) — admin can deactivate later
- Password complexity rules: Claude's discretion (something sensible for ~100 internal users)

### Dual-identity handling
- Same person can have both a Keycloak SSO account and a local account — they are separate identities with different user_ids
- Memory, conversations, and all user-scoped data are completely isolated per identity (no cross-referencing by email)
- Admin UI shows local users only — Keycloak users continue to be managed in the Keycloak admin console
- No auth-source visibility needed for MVP (no badges showing "logged in via SSO" vs "local")

### Session & token lifecycle
- Deactivation blocks on next request: validate_token checks is_active, returns 401 if false — no token blocklist needed
- Always 8-hour token expiry, no "Remember me" option — user logs in each morning
- No rate limiting on login endpoint for MVP — on-premise with ~100 employees, brute force risk is low
- Token expiry UX: Claude's discretion (pick what fits NextAuth flow best)

### Admin UX for user/group management
- Dialog-based CRUD: click "Create User" opens a modal dialog form — consistent with Phase 12 creation wizard pattern
- Single "Users" tab in /admin with two sections: Users table on top, Groups table below (or toggle)
- Simple text search box that filters by username or email — sufficient for ~100 users
- Standard confirmation dialog for destructive operations (delete user, delete group) — "Are you sure?" with entity name shown

### Claude's Discretion
- Password complexity rules (minimum length, character requirements)
- Token expiry UX (redirect to /login vs toast + redirect)
- Exact layout of Users vs Groups sections within the single tab (stacked vs toggled)
- Loading states, error messages, and edge case handling

</decisions>

<specifics>
## Specific Ideas

- Existing design doc at `docs/plans/2026-03-03-phase13-local-auth-design.md` covers: table schema (5 tables), JWT dual-issuer dispatch (HS256 local + RS256 Keycloak), API endpoint structure, login page layout (SSO button + credentials form), and plan breakdown (2 plans: backend + frontend)
- Login page: split layout with Keycloak SSO button on top, divider with "or", credentials form below
- Local JWT claims must mirror Keycloak exactly: sub, iss ("blitz-local"), email, preferred_username, realm_roles
- Role resolution: union of group roles + direct user roles — same as Keycloak's realm_roles behavior

</specifics>

<deferred>
## Deferred Ideas

- Rate limiting / brute-force protection on login endpoint — add if security review requires it
- "Remember me" / extended sessions — can add later if employees request it
- Identity linking (merge local + Keycloak by email) — separate feature if ever needed
- Session management UI (view active sessions, force logout) — separate feature
- Auth source badges in user lists — not needed at ~100 user scale

</deferred>

---

*Phase: 13-local-auth*
*Context gathered: 2026-03-03*
