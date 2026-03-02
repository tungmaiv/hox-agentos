---
phase: 05-scheduler-and-channels
plan: 01
subsystem: channels
tags: [sqlalchemy, pydantic, fastapi, multi-channel, pairing, identity-mapping]

# Dependency graph
requires:
  - phase: 04-canvas-and-workflows
    provides: "Alembic migration chain (head 012), existing ORM/route patterns"
provides:
  - "ChannelAccount and ChannelSession ORM models (channel_accounts, channel_sessions tables)"
  - "InternalMessage, MessageAction, Attachment Pydantic models"
  - "ChannelGateway class with identity mapping, session resolution, pairing flow"
  - "Channel API routes: incoming, pair, accounts, unlink"
  - "Alembic migration 013 for channel tables"
affects: [05-02, 05-03, 05-04, 05-05]

# Tech tracking
tech-stack:
  added: [httpx]
  patterns: [sidecar-gateway-pattern, pairing-code-flow, internal-message-protocol]

key-files:
  created:
    - backend/core/models/channel.py
    - backend/channels/__init__.py
    - backend/channels/models.py
    - backend/channels/gateway.py
    - backend/api/routes/channels.py
    - backend/alembic/versions/013_channel_tables.py
    - backend/tests/models/test_channel_models.py
    - backend/tests/channels/__init__.py
    - backend/tests/channels/test_models.py
    - backend/tests/channels/test_gateway.py
    - backend/tests/api/test_channel_routes.py
  modified:
    - backend/core/models/__init__.py
    - backend/main.py

key-decisions:
  - "SQLite timezone-naive datetime comparison fix: normalize pairing_expires to UTC-aware before comparing with datetime.now(timezone.utc)"
  - "send_outbound uses 3x exponential backoff (1s, 2s, 4s) per design doc locked decision"
  - "Channel routes router has /api/channels prefix built-in, registered without extra prefix in main.py"

patterns-established:
  - "InternalMessage as canonical format: all sidecars translate to/from this model"
  - "ChannelGateway singleton via get_channel_gateway() with lazy init from settings"
  - "Pairing code flow: generate in web app, /pair command from channel sidecar"

requirements-completed: [CHAN-04, CHAN-05]

# Metrics
duration: 5min
completed: 2026-02-28
---

# Phase 05 Plan 01: Channel Core Summary

**ChannelAccount/ChannelSession ORM models, InternalMessage Pydantic protocol, ChannelGateway with identity mapping and pairing flow, and channel API routes**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-27T18:40:56Z
- **Completed:** 2026-02-27T18:45:47Z
- **Tasks:** 3
- **Files modified:** 13

## Accomplishments
- ChannelAccount and ChannelSession SQLAlchemy ORM models with unique constraints and indexes
- InternalMessage canonical Pydantic model shared by all channel sidecars
- ChannelGateway with identity mapping, session resolution, 6-char pairing code flow with 10-min expiry
- Backend API routes for channel operations (incoming, pair, accounts, unlink)
- Alembic migration 013 creating channel_accounts and channel_sessions tables
- 20 new tests passing (3 ORM + 6 Pydantic + 7 gateway + 4 routes)
- Full suite: 278 tests (258 baseline + 20 new, no regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Channel ORM models, Pydantic models, and Alembic migration** - `834adf0` (feat)
2. **Task 2: ChannelGateway with identity mapping, session resolution, and pairing** - `36c60f2` (feat)
3. **Task 3: Backend API routes for channels and router registration** - `80888d2` (feat)

## Files Created/Modified
- `backend/core/models/channel.py` - ChannelAccount and ChannelSession ORM models
- `backend/core/models/__init__.py` - Register channel models for Alembic
- `backend/channels/__init__.py` - Channels package init
- `backend/channels/models.py` - InternalMessage, MessageAction, Attachment Pydantic models
- `backend/channels/gateway.py` - ChannelGateway class with all channel logic
- `backend/api/routes/channels.py` - Channel API routes with singleton gateway
- `backend/main.py` - Register channels_router
- `backend/alembic/versions/013_channel_tables.py` - Migration for channel tables
- `backend/tests/models/test_channel_models.py` - ORM model tests
- `backend/tests/channels/test_models.py` - Pydantic model tests
- `backend/tests/channels/test_gateway.py` - Gateway logic tests
- `backend/tests/api/test_channel_routes.py` - Route tests

## Decisions Made
- SQLite stores datetimes as offset-naive; added timezone normalization in handle_pairing for safe comparison with UTC-aware `datetime.now(timezone.utc)`
- send_outbound implements 3x exponential backoff retry (1s, 2s, 4s delays) per locked design decision
- Channel routes use prefix="/api/channels" on the router itself (not added via include_router prefix)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed timezone-naive datetime comparison in handle_pairing**
- **Found during:** Task 2 (ChannelGateway implementation)
- **Issue:** SQLite returns offset-naive datetimes for `pairing_expires`, but `datetime.now(timezone.utc)` is offset-aware. Comparison raises `TypeError: can't compare offset-naive and offset-aware datetimes`
- **Fix:** Added timezone normalization: if `expires.tzinfo is None`, replace with `timezone.utc` before comparison
- **Files modified:** backend/channels/gateway.py
- **Verification:** test_handle_pairing_success and test_handle_pairing_expired_code both pass
- **Committed in:** 36c60f2 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Essential fix for SQLite test compatibility. No scope creep.

## Issues Encountered
None beyond the auto-fixed timezone issue above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Channel core foundation complete -- all three sidecar plans (05-02, 05-03, 05-04) can now build on InternalMessage and ChannelGateway
- Integration wiring plan (05-05) can connect ChannelGateway to real agent invocation
- Alembic migration 013 ready to apply to production DB via `just migrate`

## Self-Check: PASSED

All 12 created/modified files verified on disk. All 3 task commit hashes (834adf0, 36c60f2, 80888d2) found in git log.

---
*Phase: 05-scheduler-and-channels*
*Completed: 2026-02-28*
