---
phase: 14-ecosystem-capabilities
plan: "03"
subsystem: ui
tags: [skill-repos, admin-ui, browse, import, security-scanner, fastapi, nextjs, pydantic]

# Dependency graph
requires:
  - phase: 14-ecosystem-capabilities
    provides: SkillRepository ORM model (migration 019), SkillDefinition ORM model, SkillImporter, SecurityScanner — all consumed by skill_repos service
  - phase: 14-ecosystem-capabilities
    provides: admin catch-all proxy at /api/admin/[...path]/route.ts — admin skill-repos routes use this automatically

provides:
  - skill_repos Python module (schemas, service, routes) — full CRUD for external repos + browse/import
  - GET/POST/DELETE/SYNC /api/admin/skill-repos — admin repo management (registry:manage)
  - GET /api/skill-repos/browse — skill browsing with search (chat permission)
  - POST /api/skill-repos/import — skill import with security scan (chat permission)
  - Admin Skill Store tab at /admin/skill-store with Repositories + Browse sub-tabs
  - Next.js proxy routes for /api/skill-repos/browse and /api/skill-repos/import
  - 26 tests covering service functions, route auth gates, and integration behavior

affects:
  - phase-15 — skill browsing surfaces ecosystem; import + pending_review flow feeds admin review queue

# Tech tracking
tech-stack:
  added: []
  patterns:
    - skill_repos module follows same service+routes separation as other backend modules
    - TDD approach: failing tests written first, then service implementation, all 26 pass
    - User proxy routes (/api/skill-repos/*) separate from admin proxy — different permission gates
    - 2-step import dialog: confirm -> security scan result prevents closing before user sees score
    - Debounced search in browse UI (300ms) reduces unnecessary backend requests

key-files:
  created:
    - backend/skill_repos/__init__.py
    - backend/skill_repos/schemas.py
    - backend/skill_repos/service.py
    - backend/skill_repos/routes.py
    - backend/tests/test_skill_repos.py
    - frontend/src/app/admin/skill-store/page.tsx
    - frontend/src/components/admin/skill-store-repositories.tsx
    - frontend/src/components/admin/skill-store-browse.tsx
    - frontend/src/app/api/skill-repos/browse/route.ts
    - frontend/src/app/api/skill-repos/import/route.ts
  modified:
    - backend/main.py (register skill_repos_admin_router + skill_repos_user_router)
    - frontend/src/app/admin/layout.tsx (add Skill Store tab to ADMIN_TABS)

key-decisions:
  - "skill_repos service uses cached_index for browse — no remote requests at browse time, only at add/sync"
  - "browse_skills filters with case-insensitive substring match on name + description in Python (not SQL)"
  - "import_from_repo creates SkillDefinition with is_active=False, status=pending_review — consistent with admin import flow"
  - "User proxy routes at /api/skill-repos/* are separate from /api/admin/* catch-all — different permission gates (chat vs registry:manage)"
  - "2-step import dialog pattern: confirm -> loading -> result ensures user sees security score before dialog closes"
  - "Skill Store page uses client-side tab state (no URL routing for sub-tabs) — simpler for MVP"

patterns-established:
  - "Module-level service functions + FastAPI router pattern — same as skill_export, openapi_bridge"
  - "User-facing proxy routes as dedicated Next.js route files (not catch-all) when permission differs from admin"
  - "Import dialog 2-step: step 1 = confirm intent, step 2 = show security result — prevents scan results being hidden"

requirements-completed:
  - ECO-03
  - ECO-04
  - ECO-05

# Metrics
duration: 10min
completed: 2026-03-04
---

# Phase 14 Plan 03: Skill Store — External Repository Management Summary

**External skill repository CRUD with admin Skill Store tab, search browse grid, and 2-step import dialog with live security scan score display**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-04T03:18:46Z
- **Completed:** 2026-03-04T03:28:46Z
- **Tasks:** 3 (1a backend service/schemas + 1b browse/import + 2 frontend)
- **Files modified:** 12 (6 created backend, 4 created frontend, 2 modified)

## Accomplishments

- Full skill_repos Python module: fetch_index validates agentskills-index.json, add/remove/sync/list repo CRUD, browse aggregates from all active repos, import calls SkillImporter + SecurityScanner
- Admin routes (registry:manage) and user routes (chat) registered in main.py with correct permissions
- Admin Skill Store tab added to /admin navigation; page with Browse/Repositories sub-tabs using client-side state
- SkillStoreRepositories: table with add (URL input dialog), sync, remove (confirm prompt) actions
- SkillStoreBrowse: 3-column responsive card grid with 300ms debounced search; 2-step import dialog shows security score (0-100) + recommendation before close
- 26 tests pass, frontend build clean, full backend regression suite 714 tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1a+1b: Backend skill_repos module (TDD)** - `d3b4e26` (feat)
2. **Task 2: Frontend Skill Store tab + proxy routes** - `a5f369f` (feat)

## Files Created/Modified

- `backend/skill_repos/__init__.py` - Module init
- `backend/skill_repos/schemas.py` - Pydantic schemas: RepoCreate, RepoInfo, SkillBrowseItem, ImportRequest, ImportResponse, IndexSchema
- `backend/skill_repos/service.py` - Service functions: fetch_index, add_repo, remove_repo, sync_repo, list_repos, browse_skills, import_from_repo
- `backend/skill_repos/routes.py` - admin_router (/api/admin/skill-repos) + user_router (/api/skill-repos)
- `backend/main.py` - Register skill_repos_admin_router + skill_repos_user_router
- `backend/tests/test_skill_repos.py` - 26 tests across 5 test classes
- `frontend/src/app/admin/skill-store/page.tsx` - Skill Store page with Browse/Repositories sub-tabs
- `frontend/src/components/admin/skill-store-repositories.tsx` - Admin repo management UI
- `frontend/src/components/admin/skill-store-browse.tsx` - Browse card grid with search + import dialog
- `frontend/src/app/admin/layout.tsx` - Added Skill Store tab to ADMIN_TABS
- `frontend/src/app/api/skill-repos/browse/route.ts` - Proxy for GET /api/skill-repos/browse
- `frontend/src/app/api/skill-repos/import/route.ts` - Proxy for POST /api/skill-repos/import

## Decisions Made

- **cached_index for browse**: browse_skills reads cached_index (JSONB) from DB — no remote HTTP calls at browse time. Freshness via explicit sync action.
- **Python-side search**: Case-insensitive substring filter in Python, not SQL — simpler for MVP at 100-user scale.
- **Separate user proxy routes**: /api/skill-repos/* files distinct from /api/admin/[...path] catch-all — different RBAC gate (chat vs registry:manage).
- **2-step import dialog**: Step 1 = confirm intent + note about security scan. Step 2 = show score/recommendation. Ensures user sees result before dismissing.
- **Client-side sub-tab state**: Simple useState for Browse/Repositories toggle — no URL routing complexity for MVP.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test mock patching approach for add_repo test**
- **Found during:** Task 1a (GREEN phase — running tests)
- **Issue:** Test patched `skill_repos.service.SkillRepository` class but `select(SkillRepository)` inside service was called before the constructor patch took effect, causing SQLAlchemy to reject the mock object
- **Fix:** Changed test to not patch SkillRepository class; instead provided a proper async refresh side_effect that populates ORM-like fields on the real SkillRepository instance created during the call
- **Files modified:** backend/tests/test_skill_repos.py
- **Verification:** All 26 tests pass
- **Committed in:** d3b4e26 (Task 1a commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in test mocking approach)
**Impact on plan:** Fix was necessary for correct test behavior. No scope creep.

## Issues Encountered

None beyond the mock patching fix documented above.

## User Setup Required

None - no external service configuration required. The skill_repos module connects to external URLs at runtime when admin adds a repo — no pre-configuration needed.

## Next Phase Readiness

- Skill Store is fully functional: admins can add/sync/remove repos, all users can browse and import
- Imported skills flow into pending_review status, feeding the existing admin review queue at /admin/skills
- Requirements ECO-03, ECO-04, ECO-05 satisfied

---
*Phase: 14-ecosystem-capabilities*
*Completed: 2026-03-04*
