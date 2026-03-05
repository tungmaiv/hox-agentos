---
phase: 17-performance-embedding-sidecar
plan: "04"
subsystem: ui
tags: [nextjs, react, tailwind, zod, admin, proxy-route]

requires:
  - phase: 17-performance-embedding-sidecar
    provides: "17-05 backend POST /api/admin/memory/reindex endpoint with JWT auth"

provides:
  - "Next.js proxy route at /api/admin/memory/reindex (JWT injection, server-side)"
  - "Admin Memory tab in admin dashboard navigation"
  - "AdminMemoryPage Client Component with reindex confirmation dialog, in-progress, and error states"

affects: [17-05, phase-18, admin-ui]

tech-stack:
  added: []
  patterns:
    - "Next.js API proxy pattern: Client Component calls /api/<resource>/route.ts which injects JWT via auth() and forwards to backend — never calls backend directly"
    - "Zod schema validation on API response in Client Component before state update"
    - "Inline destructive-action confirmation dialog (no modal library needed) with four-phase state machine"

key-files:
  created:
    - "frontend/src/app/api/admin/memory/reindex/route.ts"
    - "frontend/src/app/(authenticated)/admin/memory/page.tsx"
  modified:
    - "frontend/src/app/(authenticated)/admin/layout.tsx"

key-decisions:
  - "Proxy route uses auth() from @/auth (same as copilotkit proxy) — not getServerSession(authOptions) — matching existing project auth pattern"
  - "BACKEND_URL env var precedence: BACKEND_URL ?? NEXT_PUBLIC_API_URL ?? localhost:8000 — consistent with copilotkit proxy"
  - "Admin memory page is Client Component ('use client') with four-phase state machine (idle/confirming/submitting/in_progress/error)"
  - "Confirmation dialog is inline (not a modal) — matches plan spec and avoids extra dependencies"

patterns-established:
  - "Admin proxy route: import { auth } from '@/auth'; const session = await auth(); accessToken via type cast as Record<string,unknown>"
  - "Danger zone UI pattern: red border card section with inline confirmation replacing button on click"

requirements-completed:
  - PERF-05

duration: 3min
completed: 2026-03-05
---

# Phase 17 Plan 04: Admin Memory Reindex UI Summary

**Next.js proxy route and Admin Memory page with destructive-action confirmation dialog — closes PERF-05 frontend half with four-state UI (idle/confirming/in_progress/error) and Zod-validated API response**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-05T12:58:18Z
- **Completed:** 2026-03-05T13:01:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Created Next.js API proxy route at `/api/admin/memory/reindex` that reads JWT via `auth()` server-side and forwards POST to backend with `Authorization: Bearer` header — browser never touches the token
- Added "Memory" tab to admin dashboard navigation between "Config" and "Credentials"
- Created `AdminMemoryPage` Client Component at `/admin/memory` with full four-phase state machine, Zod-validated response schema, inline confirmation dialog, in-progress spinner with job_id display, and error banner

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Next.js proxy route** - `01a55ff` (feat)
2. **Task 2: Add Memory tab and create page** - `6bf04ad` (feat)
3. **Task 3: Verification** - (no new files — verification only; STATE.md commit below)

**Plan metadata:** (docs: complete plan — committed with STATE.md)

## Files Created/Modified
- `frontend/src/app/api/admin/memory/reindex/route.ts` - Next.js proxy route; reads JWT via `auth()`, forwards POST to backend with Authorization header
- `frontend/src/app/(authenticated)/admin/layout.tsx` - Added `{ label: "Memory", href: "/admin/memory" }` to ADMIN_TABS between Config and Credentials
- `frontend/src/app/(authenticated)/admin/memory/page.tsx` - Client Component with reindex UI: idle, confirming, submitting, in_progress, error states; Zod response schema validation

## Decisions Made
- Auth pattern mirrors `app/api/copilotkit/route.ts` exactly: `import { auth } from "@/auth"`, call `auth()`, cast to `Record<string, unknown>` to access `accessToken`
- BACKEND_URL env var precedence: `BACKEND_URL ?? NEXT_PUBLIC_API_URL ?? "http://localhost:8000"` — consistent with copilotkit proxy
- `state.phase` is a discriminated union (5 variants) for type-safe rendering logic

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- PERF-05 (Admin UI reindex button) is fully satisfied — frontend half is done
- Backend endpoint `/api/admin/memory/reindex` was delivered by 17-05 (already complete)
- The admin memory page will function end-to-end when both frontend and backend are running
- Phase 17 is now complete — all 7 plans done

## Self-Check: PASSED

- FOUND: `frontend/src/app/api/admin/memory/reindex/route.ts`
- FOUND: `frontend/src/app/(authenticated)/admin/memory/page.tsx`
- FOUND: `.planning/phases/17-performance-embedding-sidecar/17-04-SUMMARY.md`
- FOUND commit: `01a55ff` (feat: proxy route)
- FOUND commit: `6bf04ad` (feat: Memory tab + page)
- Build: `pnpm run build` exits 0, no TypeScript errors
- Tests: 743 passing (>= 719 baseline)

---
*Phase: 17-performance-embedding-sidecar*
*Completed: 2026-03-05*
