---
phase: 05-scheduler-and-channels
plan: 04
subsystem: channels
tags: [ms-teams, bot-framework, adaptive-cards, fastapi, sidecar, docker]

# Dependency graph
requires:
  - phase: 05-scheduler-and-channels
    provides: "InternalMessage Pydantic model, ChannelGateway, channel API routes"
provides:
  - "MS Teams sidecar FastAPI service (port 9003)"
  - "TeamsAPI Bot Framework Connector wrapper with OAuth2 token caching"
  - "Adaptive Card builder with Action.Submit buttons"
  - "Bot Framework JWT validation"
  - "teams-gateway Docker Compose service"
affects: [05-05]

# Tech tracking
tech-stack:
  added: [PyJWT, cryptography]
  patterns: [bot-framework-activity-protocol, adaptive-card-action-submit, mention-filter-pattern]

key-files:
  created:
    - channel-gateways/teams/pyproject.toml
    - channel-gateways/teams/teams_api.py
    - channel-gateways/teams/main.py
    - channel-gateways/teams/Dockerfile
    - channel-gateways/teams/tests/__init__.py
    - channel-gateways/teams/tests/test_webhook.py
    - channel-gateways/teams/tests/test_send.py
  modified:
    - docker-compose.yml

key-decisions:
  - "Direct HTTP calls to Bot Framework Connector API via httpx instead of heavy botbuilder-core SDK -- consistent with Telegram/WhatsApp sidecar patterns"
  - "MVP token validation: decode without signature verification, check issuer and audience claims -- full JWKS rotation handling deferred"
  - "hatch build config packages=['.'] required since flat project layout does not match package name convention"

patterns-established:
  - "Bot Framework Activity protocol: parse inbound Activities, send outbound via Connector API"
  - "Adaptive Card with Action.Submit: card body + action buttons, invoke activity handling for callbacks"
  - "@mention filter: check entities for bot mention in team channels, skip non-mentioned messages"

requirements-completed: [CHAN-03]

# Metrics
duration: 4min
completed: 2026-02-28
---

# Phase 05 Plan 04: MS Teams Sidecar Summary

**MS Teams Bot Framework sidecar with Activity parsing, @mention filtering, Adaptive Card Action.Submit support, and Docker Compose integration on port 9003**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-27T18:48:55Z
- **Completed:** 2026-02-27T18:53:05Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- TeamsAPI wrapper with OAuth2 client_credentials token caching, Connector API send/reply, Adaptive Card builder, and JWT validation
- FastAPI sidecar handling Bot Framework message and invoke Activities, @mention filtering for team channels, typing indicator, attachment rejection, message truncation at 4096 chars
- Dockerfile and Docker Compose service (teams-gateway) on port 9003 with blitz-net and backend dependency
- 8 tests covering all webhook and send functionality

## Task Commits

Each task was committed atomically:

1. **Task 1: Teams Bot Framework wrapper and sidecar FastAPI app** - `d707714` (feat)
2. **Task 2: Dockerfile and Docker Compose service for Teams sidecar** - `9ae3347` (feat)

## Files Created/Modified
- `channel-gateways/teams/pyproject.toml` - Project config with FastAPI, httpx, PyJWT, cryptography deps
- `channel-gateways/teams/teams_api.py` - TeamsAPI class: token mgmt, send/reply/typing, Adaptive Cards, JWT validation
- `channel-gateways/teams/main.py` - FastAPI app with /webhook, /send, /health endpoints
- `channel-gateways/teams/Dockerfile` - Python 3.12-slim image, curl healthcheck, uvicorn on port 9003
- `channel-gateways/teams/tests/__init__.py` - Test package init
- `channel-gateways/teams/tests/test_webhook.py` - 5 webhook tests: message, invoke, @mention, non-mention, attachment
- `channel-gateways/teams/tests/test_send.py` - 3 send tests: text, Adaptive Card, threaded reply
- `docker-compose.yml` - Added teams-gateway service on port 9003

## Decisions Made
- Used direct httpx calls to Bot Framework Connector API instead of botbuilder-core SDK (heavyweight, Azure Functions oriented); keeps sidecar lightweight and consistent with Telegram/WhatsApp patterns
- MVP token validation decodes JWT without signature verification, checks issuer (api.botframework.com) and audience (app_id); full JWKS rotation handling deferred to hardening phase
- Added `[tool.hatch.build.targets.wheel] packages = ["."]` to pyproject.toml since flat project layout (main.py, teams_api.py at root) does not match hatchling's default package name convention

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added hatch build config for flat project layout**
- **Found during:** Task 1 (dependency installation)
- **Issue:** `uv sync` failed with "Unable to determine which files to ship" because hatchling expects a directory matching the package name (blitz_teams_gateway/)
- **Fix:** Added `[tool.hatch.build.targets.wheel] packages = ["."]` to pyproject.toml
- **Files modified:** channel-gateways/teams/pyproject.toml
- **Verification:** `uv sync` succeeds, all 8 tests pass
- **Committed in:** d707714 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential fix for build tooling. No scope creep.

## Issues Encountered
None beyond the auto-fixed hatch build config above.

## User Setup Required
MS Teams requires Azure Bot Service registration. Environment variables:
- `TEAMS_APP_ID` - Azure Portal > Bot Service > App ID
- `TEAMS_APP_PASSWORD` - Azure Portal > Bot Service > App Password (client secret)
- Set messaging endpoint to `https://<public-url>:9003/webhook` in Azure Bot Configuration
- Install bot in Teams tenant via Teams Admin Center > Manage apps > Upload custom app

## Next Phase Readiness
- All three channel sidecars (Telegram, WhatsApp, Teams) now have Docker services defined
- Integration wiring plan (05-05) can connect all sidecars to ChannelGateway agent invocation
- Teams sidecar ready for end-to-end testing once Azure Bot Service is configured

## Self-Check: PASSED

All 7 created files and 1 modified file verified on disk. Both task commit hashes (d707714, 9ae3347) found in git log.

---
*Phase: 05-scheduler-and-channels*
*Completed: 2026-02-28*
