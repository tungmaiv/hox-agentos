---
created: 2026-03-15T06:51:58.504Z
title: "Implement Email System & Notifications (Topic #18)"
area: channels
priority: medium
target: v1.4-infrastructure
effort: 6 weeks
existing_code: 5%
depends_on: ["topic-15-scheduler"]
design_doc: docs/enhancement/topics/18-email-system-channel-notifications/00-specification.md
files:
  - backend/agents/subagents/email_agent.py
  - backend/core/models/channel.py
  - channel-gateways/
---

## Problem

Email agent returns hardcoded mock data. No real email integration exists. No notification routing system — scheduler, HITL, and system events have no way to notify users via email, Telegram, or other channels.

**IMPORTANT:** Start OAuth application registration for Google Workspace and Microsoft 365 immediately when beginning this work — verification takes 1-4 weeks lead time.

## What Exists (5%)

- Mock `email_agent.py` with hardcoded data (schema matches real shape for future wiring)
- Channel architecture pattern exists: Telegram, WhatsApp, Teams gateways in `channel-gateways/`
- `ChannelAccount`, `ChannelSession` models in `backend/core/models/channel.py`
- `UserCredential` model for encrypted OAuth tokens (AES-256)
- Scheduler (#15) engine exists (Celery + beat)

## What's Needed

- **Email sidecar service** (port 8003) — standalone email service following channel gateway pattern
- **OAuth integration** — Google Workspace (Gmail API) and Microsoft 365 (Graph API) OAuth flows
- **IMAP/SMTP client** — real email sending/receiving, replacing mock data
- **`user_notification_preferences` table** — per-user notification routing rules
- **Notification routing system** — logic to deliver notifications by channel (email vs chat vs Telegram)
- **Email templates** — template management system for system emails
- **System email configuration** — admin settings for SMTP/IMAP
- **HITL email notifications** — notify users of pending approvals via email
- **Email-as-channel adapter** — add email as a channel type alongside Telegram/WhatsApp/Teams

## Solution

Follow specification at `docs/enhancement/topics/18-email-system-channel-notifications/00-specification.md`. Sidecar pattern, hybrid auth, centralized notification routing.
