---
phase: 05-scheduler-and-channels
plan: 02
subsystem: channels
tags: [telegram, bot-api, fastapi, sidecar, docker, webhooks, markdown-v2, inline-keyboard]

# Dependency graph
requires:
  - phase: 05-scheduler-and-channels
    plan: 01
    provides: "InternalMessage Pydantic model, ChannelGateway, /api/channels/incoming endpoint"
provides:
  - "Telegram sidecar FastAPI service (channel-gateways/telegram)"
  - "TelegramAPI wrapper: sendMessage, sendChatAction, setWebhook, MarkdownV2 escaping, InlineKeyboard"
  - "Webhook handler with group @mention filtering and media rejection"
  - "Outbound send handler with MarkdownV2 formatting, truncation, InlineKeyboard"
  - "Dockerfile and Docker Compose service on port 9001"
affects: [05-05]

# Tech tracking
tech-stack:
  added: [telegram-bot-api]
  patterns: [sidecar-fastapi-pattern, markdown-v2-escaping, inline-keyboard-builder, webhook-registration-on-startup]

key-files:
  created:
    - channel-gateways/telegram/pyproject.toml
    - channel-gateways/telegram/telegram_api.py
    - channel-gateways/telegram/main.py
    - channel-gateways/telegram/tests/__init__.py
    - channel-gateways/telegram/tests/test_webhook.py
    - channel-gateways/telegram/tests/test_send.py
    - channel-gateways/telegram/Dockerfile
  modified:
    - docker-compose.yml

key-decisions:
  - "Sidecar defines its own InternalMessage Pydantic model (mirrors backend channels.models) to avoid cross-project imports"
  - "MarkdownV2 escaping via regex substitution of all 18 special characters"
  - "InlineKeyboard buttons arranged in rows of 3, max 100 buttons per Telegram limit"
  - "Webhook registration on startup via lifespan context manager, skipped if TELEGRAM_WEBHOOK_URL not set"
  - "Group @mention detection via entity type 'mention' matching BOT_USERNAME; bot_command entities also accepted"

patterns-established:
  - "Telegram sidecar pattern: standalone FastAPI on port 9001, /webhook + /send + /health endpoints"
  - "Media rejection pattern: non-text messages get 'I can only process text messages' response"
  - "Message truncation pattern: cap at 4096 chars with '... (response truncated)' suffix"

requirements-completed: [CHAN-01]

# Metrics
duration: 5min
completed: 2026-02-28
---

# Phase 05 Plan 02: Telegram Sidecar Summary

**Telegram Bot API sidecar with webhook inbound (text, callbacks, group @mentions), MarkdownV2 outbound with InlineKeyboard, Dockerfile on port 9001**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-27T18:48:48Z
- **Completed:** 2026-02-27T18:53:41Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- TelegramAPI wrapper with sendMessage (MarkdownV2 + InlineKeyboard), sendChatAction, setWebhook
- FastAPI sidecar with /webhook (inbound translation), /send (outbound formatting), /health
- Webhook handles: text messages, callback queries, group @mention filtering, media-only rejection
- Outbound handles: MarkdownV2 character escaping, 4096-char truncation, InlineKeyboard from actions, reply threading
- 11 tests passing (6 webhook + 5 send)
- Dockerfile and Docker Compose telegram-gateway service on port 9001 with blitz-net network

## Task Commits

Each task was committed atomically:

1. **Task 1: Telegram API wrapper and sidecar FastAPI app** - `4a8423d` (feat)
2. **Task 2: Dockerfile and Docker Compose service** - `29242fc` (feat)

## Files Created/Modified
- `channel-gateways/telegram/pyproject.toml` - Project definition with fastapi, httpx, structlog, pydantic deps
- `channel-gateways/telegram/telegram_api.py` - TelegramAPI class: sendMessage, sendChatAction, setWebhook, escape_markdown_v2, build_inline_keyboard
- `channel-gateways/telegram/main.py` - FastAPI sidecar: /webhook, /send, /health; group @mention filter; media rejection; typing indicator
- `channel-gateways/telegram/tests/__init__.py` - Tests package init
- `channel-gateways/telegram/tests/test_webhook.py` - 6 tests: text forward, callback query, group mention, group ignore, attachment reject, empty update
- `channel-gateways/telegram/tests/test_send.py` - 5 tests: text send, reply-to, missing chat_id, inline keyboard, truncation
- `channel-gateways/telegram/Dockerfile` - python:3.12-slim, pip install, uvicorn on port 9001, curl healthcheck
- `docker-compose.yml` - Added telegram-gateway service on port 9001, blitz-net, depends_on backend

## Decisions Made
- Sidecar defines its own InternalMessage Pydantic model (identical structure to backend channels.models) to keep the sidecar fully standalone with no cross-project imports
- MarkdownV2 escaping uses regex substitution for all 18 Telegram special characters: `_*[]()~>#+-=|{}.!\`
- InlineKeyboard buttons arranged in rows of 3, capped at 100 per Telegram API limit; excess silently dropped
- Webhook registration happens at startup via FastAPI lifespan context manager; gracefully skipped if TELEGRAM_WEBHOOK_URL not set
- Group @mention detection checks entity type "mention" matching BOT_USERNAME and also accepts "bot_command" entities

## Deviations from Plan

### Notes

Task 1 code was already committed in `4a8423d` by a prior executor agent (commit was labeled as 05-03 but contained both Telegram and WhatsApp sidecar code). The existing code matched the plan exactly, so no re-implementation was needed. Task 2 (Dockerfile and Docker Compose) was not yet done and was implemented fresh.

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added hatch wheel build config for flat module layout**
- **Found during:** Task 1 verification (uv sync failed)
- **Issue:** hatchling defaulted to looking for `src/foo` package layout; the sidecar uses flat modules (main.py, telegram_api.py)
- **Fix:** Added `[tool.hatch.build.targets.wheel] packages = ["."]` and `pythonpath = ["."]` to pyproject.toml
- **Files modified:** channel-gateways/telegram/pyproject.toml
- **Verification:** uv sync succeeds, all 11 tests pass
- **Committed in:** Already in 4a8423d (prior agent made same fix)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential fix for build system. No scope creep.

## Issues Encountered
None beyond the auto-fixed build config issue.

## User Setup Required
Telegram Bot API requires external configuration:
- `TELEGRAM_BOT_TOKEN`: Obtain from Telegram @BotFather via /newbot command
- `TELEGRAM_WEBHOOK_URL`: External URL where Telegram sends webhooks (e.g., ngrok URL + /webhook)
- `BACKEND_URL`: Backend internal URL (default http://backend:8000, no change needed in Docker)

## Next Phase Readiness
- Telegram sidecar complete and ready for integration wiring in 05-05
- Docker Compose service configured on blitz-net with backend dependency
- 11 tests provide confidence in webhook parsing, outbound formatting, and edge cases
- Remaining sidecars (WhatsApp 05-03, Teams 05-04) can be built in parallel

## Self-Check: PASSED

All 8 created/modified files verified on disk. Both task commit hashes (4a8423d, 29242fc) found in git log.

---
*Phase: 05-scheduler-and-channels*
*Completed: 2026-02-28*
