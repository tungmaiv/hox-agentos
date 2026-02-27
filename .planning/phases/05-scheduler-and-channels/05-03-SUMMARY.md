---
phase: 05-scheduler-and-channels
plan: 03
subsystem: channels
tags: [whatsapp, cloud-api, fastapi, sidecar, docker, interactive-messages]

# Dependency graph
requires:
  - phase: 05-scheduler-and-channels
    plan: 01
    provides: "InternalMessage Pydantic model, ChannelGateway, channel API routes"
provides:
  - "WhatsApp Cloud API wrapper (send_text, send_interactive, strip_markdown)"
  - "WhatsApp sidecar FastAPI service (webhook verification, inbound parsing, outbound send)"
  - "WhatsApp sidecar Dockerfile and Docker Compose whatsapp-gateway service on port 9002"
affects: [05-05]

# Tech tracking
tech-stack:
  added: [whatsapp-cloud-api-v21]
  patterns: [sidecar-gateway-pattern, webhook-challenge-response, interactive-button-messages]

key-files:
  created:
    - channel-gateways/whatsapp/pyproject.toml
    - channel-gateways/whatsapp/whatsapp_api.py
    - channel-gateways/whatsapp/main.py
    - channel-gateways/whatsapp/Dockerfile
    - channel-gateways/whatsapp/tests/__init__.py
    - channel-gateways/whatsapp/tests/test_webhook.py
    - channel-gateways/whatsapp/tests/test_send.py
  modified:
    - docker-compose.yml

key-decisions:
  - "Button capping applied at both /send endpoint (main.py) and WhatsApp API wrapper for defense in depth"
  - "Attachment rejection sends text reply to user explaining text-only MVP limitation"
  - "Interactive button replies parsed with callback_data in metadata for downstream processing"

patterns-established:
  - "WhatsApp webhook verification: GET /webhook with hub.mode+hub.verify_token challenge-response"
  - "WhatsApp Cloud API v21.0 message format for text and interactive button types"
  - "strip_markdown utility: **bold** -> *bold*, code blocks stripped, links to plain text"

requirements-completed: [CHAN-02]

# Metrics
duration: 3min
completed: 2026-02-28
---

# Phase 05 Plan 03: WhatsApp Channel Sidecar Summary

**WhatsApp Cloud API sidecar with webhook verification, text/interactive message support, 3-button cap, markdown stripping, and Docker Compose service on port 9002**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-27T18:48:53Z
- **Completed:** 2026-02-27T18:52:33Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- WhatsApp Cloud API wrapper with send_text, send_interactive, and strip_markdown methods
- FastAPI sidecar with webhook verification (GET), inbound message parsing (POST), outbound send, and health check
- Inbound handling: text messages, interactive button replies with callback_data, attachment rejection (text-only MVP)
- Outbound: markdown stripping (bold/italic preserved, code blocks/links converted), 4096-char truncation, 3-button cap
- Dockerfile with python:3.12-slim, healthcheck, and Docker Compose whatsapp-gateway service on port 9002
- 9 tests passing (5 webhook + 4 send)

## Task Commits

Each task was committed atomically:

1. **Task 1: WhatsApp Cloud API wrapper and sidecar FastAPI app** - `4a8423d` (feat)
2. **Task 2: Dockerfile and Docker Compose service for WhatsApp sidecar** - `716d0ea` (feat)

## Files Created/Modified
- `channel-gateways/whatsapp/pyproject.toml` - Project definition with fastapi, httpx, structlog, pydantic deps
- `channel-gateways/whatsapp/whatsapp_api.py` - WhatsApp Cloud API wrapper (send_text, send_interactive, strip_markdown)
- `channel-gateways/whatsapp/main.py` - FastAPI sidecar (GET/POST /webhook, POST /send, GET /health)
- `channel-gateways/whatsapp/Dockerfile` - Docker image for WhatsApp sidecar (python:3.12-slim, port 9002)
- `channel-gateways/whatsapp/tests/__init__.py` - Test package init
- `channel-gateways/whatsapp/tests/test_webhook.py` - 5 webhook tests (verification, text, interactive, attachment)
- `channel-gateways/whatsapp/tests/test_send.py` - 4 send tests (text, interactive, button cap, markdown strip)
- `docker-compose.yml` - Added whatsapp-gateway service on blitz-net, port 9002

## Decisions Made
- Button capping applied at both /send endpoint and WhatsApp API wrapper for defense in depth; the plan specified capping in send_interactive only, but /send endpoint also caps before calling the API to ensure correctness when API is mocked in tests
- Attachment rejection sends a polite text reply ("I can only process text messages") rather than silently ignoring, improving user experience
- Interactive button replies extract callback_data from button_reply.id into metadata dict for downstream processing by ChannelGateway

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed button cap not applying at /send endpoint level**
- **Found during:** Task 1 (test_buttons_capped_at_3)
- **Issue:** Button capping was implemented in whatsapp_api.py send_interactive(), but the /send endpoint in main.py passed all buttons to the API. When the API is mocked in tests, the capping never executes, and 5 buttons pass through.
- **Fix:** Added `msg.actions[:3]` slicing in main.py /send endpoint before building button list
- **Files modified:** channel-gateways/whatsapp/main.py
- **Verification:** test_buttons_capped_at_3 passes (asserts exactly 3 buttons sent)
- **Committed in:** 4a8423d (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Essential fix for correct 3-button cap behavior at the endpoint level. No scope creep.

## Issues Encountered
- `hatchling` build required `[tool.hatch.build.targets.wheel] packages = ["."]` since the project uses flat layout (no package directory matching project name). Added to pyproject.toml during uv sync.
- `uv add --dev` used to install pytest/pytest-asyncio into dev dependency group since `uv sync` only installs optional-dependencies if explicitly requested.

## User Setup Required
WhatsApp Cloud API requires manual configuration:
- **WHATSAPP_ACCESS_TOKEN**: From Meta for Developers -> WhatsApp -> API Setup -> Temporary access token
- **WHATSAPP_PHONE_NUMBER_ID**: From Meta for Developers -> WhatsApp -> API Setup -> Phone number ID
- **WHATSAPP_VERIFY_TOKEN**: Self-chosen string for webhook verification handshake
- **Webhook URL registration**: In Meta for Developers -> WhatsApp -> Configuration -> Webhook URL, point to the whatsapp-gateway service public URL

## Next Phase Readiness
- WhatsApp sidecar complete, ready for integration wiring (05-05)
- Docker Compose service validated with `docker compose config`
- All 9 tests passing, webhook verification and message handling verified
- Pairs with Telegram sidecar (05-02) as second channel adapter

## Self-Check: PASSED

All 8 created/modified files verified on disk. Both task commit hashes (4a8423d, 716d0ea) found in git log.

---
*Phase: 05-scheduler-and-channels*
*Completed: 2026-02-28*
