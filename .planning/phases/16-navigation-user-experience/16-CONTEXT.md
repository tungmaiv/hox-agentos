# Phase 16: Navigation & User Experience - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can navigate the entire application from a persistent navigation rail and manage their profile and preferences from a dedicated page. This phase covers the nav rail component, route group restructuring, profile page (account info + LLM preferences + custom instructions), settings slim-down, and mobile navigation. Backend work includes user_preferences table, preference API endpoints, and agent system prompt injection. Identity configuration (Keycloak-optional boot) is Phase 18.

</domain>

<decisions>
## Implementation Decisions

### Nav rail visual style
- Dark sidebar (charcoal/navy background with light icons) — provides clear visual separation from content area
- Fixed 64px width, icon-only with tooltip on hover — no expand/collapse mechanism
- "B" monogram logo at the top in a rounded square
- Active indicator: 2-3px blue/accent left border + slightly lighter background on the active icon area

### Nav rail items
- Top group: Chat (MessageSquare), Workflows (GitBranch), Skills (Zap)
- Bottom group: Admin (Shield, role-gated), Settings (Settings icon), Profile (User icon)
- Admin item visible only to users with `admin`, `developer`, or `it-admin` roles
- Desktop nav rail hidden on mobile (`hidden md:flex`); mobile tab bar hidden on desktop (`md:hidden`)

### Profile page layout
- Single scrollable page with card sections — no tabs
- Sections in order: Account Info, Custom Instructions, LLM Preferences, Sign Out button
- Account Info shows: name, email, auth provider badge (SSO/Local), roles, session expiry as relative time ("Expires in 6h 42m", updates every minute)
- Password change: inline expandable form (not a modal) — visible only for local auth users
- Custom instructions: textarea with manual Save button (moved from /settings)
- LLM preferences: auto-save on toggle/radio change with brief "Saved" indicator — no save button needed for quick controls

### Settings restructuring
- Settings stays as a separate nav rail item — "app config" (channels, memory) vs Profile as "personal" (account, preferences)
- Remove custom instructions textarea and chat preferences link from /settings (moved to /profile)
- Keep: Channel Linking (Telegram/WhatsApp/Teams), Memory Management
- Settings page keeps current card-grid layout with items that moved to Profile removed

### Mobile navigation
- Bottom tab bar with 5 items: Chat, Workflows, Skills, Settings, Profile — always fixed (no hide-on-scroll)
- Tab bar replaces the hamburger toggle — conversation sidebar opens as a drawer overlay via a list icon in the chat header
- Admin access on mobile: link on the profile page, visible only to admin-role users — no 6th tab
- Nav rail is hidden on mobile; tab bar is hidden on desktop

### Claude's Discretion
- Exact dark sidebar color values (charcoal shade, icon colors, hover states)
- Tooltip implementation details (delay, position, animation)
- Mobile drawer animation and overlay styling
- Card section border/shadow styling on profile page
- Lucide icon package integration specifics

</decisions>

<specifics>
## Specific Ideas

- Dark nav rail should feel like Linear or VS Code activity bar — enterprise-grade, not playful
- Profile page sections should use clean card-style containers with subtle shadows — "modern admin" feel consistent with the existing admin dashboard
- Auto-save on preference toggles should show a brief inline "Saved" checkmark that fades after 1-2 seconds — not a toast notification
- The conversation sidebar drawer on mobile should use the same slide-in animation and overlay that already exists in `chat-layout.tsx`

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SignOutButton` component (`components/sign-out-button.tsx`): full Keycloak end-session + local auth logout — reuse on profile page
- `AuthErrorToasts` component: Sonner toaster already at app root — available for any toast notifications
- `ConversationSidebar` (`components/chat/conversation-sidebar.tsx`): has Settings link + SignOut in footer — may need adjustment when nav rail provides these
- Admin layout (`app/admin/layout.tsx`): RBAC role check pattern (`ADMIN_ROLES` array + `realmRoles` extraction) — reuse same pattern for nav rail role gating
- Settings page (`app/settings/page.tsx`): card grid layout with sub-page links — pattern to preserve

### Established Patterns
- `SessionProvider` wraps entire app in root layout with `refetchOnWindowFocus` — session data available everywhere
- Server Components call `auth()` for session; Client Components use `useSession()`
- Middleware allowlist protects all routes by default (Phase 15)
- Admin RBAC checks `realmRoles` from session token (both flat and nested paths)
- Existing user instructions API: `GET/PUT /api/user/instructions/` — no backend change needed for this

### Integration Points
- New `(authenticated)/layout.tsx` — wraps all auth'd pages with NavRail + MobileTabBar
- Move existing page directories into `(authenticated)/` route group
- New `user_preferences` table + Alembic migration 020
- New `GET/PUT /api/users/me/preferences` endpoints
- `master_agent.py` — inject preference directives into agent system prompt via PromptLoader
- Root layout stays unchanged (SessionProvider + AuthErrorToasts)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 16-navigation-user-experience*
*Context gathered: 2026-03-05*
