# Phase 5: Scheduler and Channels - Context

**Gathered:** 2026-02-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Add multi-channel messaging to Blitz AgentOS. Users interact with the master agent from Telegram, WhatsApp, and MS Teams with the same capabilities as web chat. Each channel runs as an isolated Docker sidecar service. Identity pairing maps external platform users to Blitz user IDs via 6-digit codes.

Scheduler (cron triggers, Celery workflow execution) is already built in Phase 4 — this phase is purely channel integration.

</domain>

<decisions>
## Implementation Decisions

### Architecture (locked from brainstorming)
- Sidecar Docker services: one FastAPI container per channel (Telegram :9001, WhatsApp :9002, Teams :9003)
- Each sidecar has `/webhook` (inbound) and `/send` (outbound) endpoints
- Backend owns all business logic: identity mapping, agent routing, security gates
- InternalMessage is the canonical Pydantic model shared between all sidecars and backend
- Identity pairing via 6-digit code generated in web UI, sent to bot as `/pair CODE`
- WhatsApp uses Official Cloud API (not Baileys)
- Rich content: Text + Markdown + inline buttons (Telegram InlineKeyboard, WhatsApp Interactive, Teams Adaptive Cards)

### Group/mention behavior
- Bot responds to @mentions only in Telegram groups and Teams channels — not all messages
- Identity resolution uses the mentioning user's personal pairing (not group-level pairing)
- Unpaired users who @mention the bot in a group get the standard pairing prompt
- Responses are threaded (reply to the original message) to keep group chat organized
- WhatsApp is DM-only — no group support for MVP (WhatsApp groups lack clean @mention support)

### Error & retry policy
- Outbound message delivery: retry 3x with exponential backoff (1s, 2s, 4s), then drop and log failure
- Agent response timeout: 60 seconds per channel message
- On timeout/error: send friendly error message ("Sorry, I couldn't process your request. Please try again.")
- Typing indicators: send where platform supports it (Telegram sendChatAction, Teams typing Activity; skip WhatsApp)

### Message format mapping
- Markdown translation: best-effort per platform
  - Telegram: MarkdownV2 (native, full support)
  - WhatsApp: bold/italic only (strip code blocks, links as plain text)
  - Teams: full markdown via Adaptive Cards
- Long responses: truncate at platform character limit (4096 chars) with "... (response truncated)"
- Button overflow: show up to platform max (WhatsApp 3, Telegram ~100), drop excess buttons silently
- Attachments: text-only for MVP — if user sends image/file, respond "I can only process text messages at the moment."

### Pairing UX (settings page)
- Layout: one card per channel (Telegram, WhatsApp, Teams) with platform icon, status, and action button
- Pairing code display: live countdown timer showing "Code expires in M:SS"
- Unlink action: confirmation dialog ("Are you sure you want to unlink Telegram?")
- Already-paired state: show "Linked as @username" with unlink button — no re-pair flow from link button

### Claude's Discretion
- Exact Dockerfile base image and Python version for sidecars
- Specific markdown-to-MarkdownV2 escaping implementation
- Typing indicator refresh interval
- Exact retry backoff implementation details
- Settings page card styling and responsive layout

</decisions>

<specifics>
## Specific Ideas

- Approved design document: `docs/plans/2026-02-28-phase-5-channels-design.md` — contains full architecture diagram, data models, sidecar designs, ChannelGateway class, API routes, and testing strategy
- Implementation plan: `docs/plans/2026-02-28-phase-5-implementation.md` — 5 plans with complete TDD code and file paths
- Existing stubs to wire: `backend/agents/node_handlers.py` channel_output_node (line 182), `backend/agents/delivery_router.py` Telegram/Teams stubs
- Frontend settings page at `frontend/src/app/settings/page.tsx` already has nav grid pattern to follow

</specifics>

<deferred>
## Deferred Ideas

- File/image attachment support in channel messages — future enhancement after MVP text-only
- WhatsApp group support — blocked by platform @mention limitations
- Message queuing in Redis for offline sidecar recovery — keep simple with retry-then-drop for MVP
- Re-pairing flow (link different account without unlinking first) — unlink + re-link is sufficient

</deferred>

---

*Phase: 05-scheduler-and-channels*
*Context gathered: 2026-02-28*
