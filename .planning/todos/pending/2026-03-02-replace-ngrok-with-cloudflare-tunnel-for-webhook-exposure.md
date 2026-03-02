---
created: 2026-03-02T03:26:08.205Z
title: Replace ngrok with Cloudflare Tunnel for webhook exposure
area: tooling
files:
  - channel-gateways/telegram/
  - channel-gateways/whatsapp/
  - channel-gateways/teams/
  - docker-compose.yml
---

## Problem

AgentOS currently uses ngrok to expose local webhooks so that Telegram, WhatsApp, and Microsoft Teams can deliver messages to the channel gateways. ngrok has limitations:
- Requires a paid plan for stable URLs / custom domains
- Introduces an external dependency that may have reliability issues
- The URL changes on free tier restarts, requiring webhook re-registration each time

Cloudflare Tunnel (`cloudflared`) provides a free, stable, named tunnel that doesn't require a paid plan and integrates cleanly with a self-hosted setup.

## Solution

1. Remove ngrok from the project (config, docker-compose, docs)
2. Add `cloudflared` as a Docker service in `docker-compose.yml` (or run as a sidecar)
3. Configure a named Cloudflare Tunnel pointed at the three channel gateway ports:
   - Telegram gateway (channel-gateways/telegram)
   - WhatsApp gateway (channel-gateways/whatsapp)
   - MS Teams gateway (channel-gateways/teams)
4. Update webhook registration scripts/docs to use the stable Cloudflare Tunnel URL
5. Store tunnel token in `.env` / `.dev-secrets` (never hardcoded)
6. Scope tunnel exposure to **only** the three webhook endpoints — do NOT expose backend or frontend via the tunnel
7. Update `docs/dev-context.md` with new tunnel URL patterns and setup instructions
