---
status: complete
phase: 22-skill-platform-d-sharing-marketplace
source: [22-01-SUMMARY.md, 22-02-SUMMARY.md, 22-03-SUMMARY.md]
started: 2026-03-09T00:00:00Z
updated: 2026-03-09T16:30:00Z
---

## Current Test

number: 1
name: Promote a Skill (Admin)
expected: |
  On /admin/skills, open a skill card's action area. A "Promote" button is visible.
  Clicking it sends PATCH /api/admin/skills/{id}/promote and an amber "Promoted" badge
  appears on the card. The button label changes to "Unpromote".
awaiting: user response

## Tests

### 1. Promote a Skill (Admin)
expected: On /admin/skills, open a skill card's action area. A "Promote" button is visible. Clicking it sends PATCH /api/admin/skills/{id}/promote and an amber "Promoted" badge appears on the card. The button label changes to "Unpromote".
result: pass

### 2. Unpromote a Skill (Admin)
expected: On a card already showing an amber "Promoted" badge and "Unpromote" button, clicking "Unpromote" removes the badge and reverts the button label back to "Promote".
result: pass

### 3. Share Dialog Opens (Admin)
expected: On /admin/skills, clicking "Share with user..." in a skill card's action area opens a modal dialog with a user search input field and a "Currently shared with" list (empty initially).
result: pass

### 4. User Search in Share Dialog (Admin)
expected: Typing a name or email in the share dialog search field shows a dropdown of matching users from /api/admin/users. Clicking a user from the dropdown triggers POST /api/admin/skills/{id}/share and they appear in the "Currently shared with" list. Card shows blue "Shared (N)" badge after closing.
result: pass
note: Required 3 fixes — wrong URL (/api/admin/users→/api/admin/local/users), UUID display replaced with username/email, share_count badge added to card.

### 5. Revoke Share (Admin)
expected: In the share dialog, a user listed under "Currently shared with" has a "Revoke" button. Clicking it calls DELETE /api/admin/skills/{id}/share/{user_id} and the user disappears from the list without page reload. Card badge updates immediately.
result: pass
note: Required optimistic shareCountOverrides state — calling setState inside setState callback was unreliable. Fixed to compute newCount from shares.length before update, call setters separately.

### 6. Featured Skills Section (User)
expected: On /skills, when at least one skill is promoted by admin, an amber "Featured Skills" section appears above the main skill grid. When no skills are promoted, this section is absent entirely.
result: pass
note: Promoted skills intentionally appear in both Featured section and main grid (app store pattern — by design, not a bug).

### 7. Shared Badge on User Skills Page
expected: Skills that an admin has shared with the current user show a green "Shared" badge in the main skill grid on /skills. Skills not shared with that user show no such badge.
result: pass
note: Required root-cause debug — UUID mismatch between LocalUser.id (used by share dialog) and Keycloak sub (used by JWT). Fixed by adding GET /api/admin/keycloak/users endpoint that merges both local DB users and Keycloak users, deduplicating by email with Keycloak ID taking precedence. Also fixed list_skill_shares to resolve identity via Keycloak admin API when user_id is not in local_users.

### 8. Export ZIP Download
expected: On /skills, clicking the Export button on a skill card triggers a browser file download. The downloaded file has a .zip extension and a name matching the skill (e.g., my-skill-1.0.0.zip).
result: pass
note: Required adding frontend/src/app/api/skills/[...path]/route.ts catch-all proxy. The root /api/skills/route.ts only handled listing; sub-paths like /{id}/export had no Next.js proxy and silently failed for regular users. Admin export worked because it used /api/admin/[...path] catch-all.

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0

## Gaps

- Share dialog user search now queries both local DB and Keycloak (merged by email, Keycloak ID wins). In dual-auth environments, admins should be aware that sharing with a user who exists in both systems will use their Keycloak identity (the JWT sub they authenticate with).
