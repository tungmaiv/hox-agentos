# Phase 11-01: Cloudflare Tunnel Wiring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire the existing Cloudflare Tunnel on the remote LXC to the three channel gateway Docker services so Telegram/WhatsApp/Teams webhooks work without ngrok.

**Architecture:** The `cloudflared` daemon on LXC `172.16.155.118` is already connected to Cloudflare. Three ingress rules are added to its config pointing each subdomain to the workstation's Tailscale IP (`100.68.144.118`) at the respective gateway port (9001/9002/9003). Local docker-compose.yml gains the two missing webhook URL env vars. All ngrok references are removed from docs.

**Tech Stack:** Cloudflare Tunnel (`cloudflared`), Tailscale, Docker Compose, bash

---

## Context

The channel gateways already run correctly locally:
- `telegram-gateway` → port 9001 (has `TELEGRAM_WEBHOOK_URL` in compose)
- `whatsapp-gateway` → port 9002 (missing `WHATSAPP_WEBHOOK_URL`)
- `teams-gateway` → port 9003 (missing `TEAMS_WEBHOOK_URL`)

The LXC is the tunnel host, not the workstation. No `cloudflared` Docker service is added locally — the LXC tunnel is always-on.

**Files to touch:**
- Modify: `docker-compose.yml` (add 2 missing webhook URL env vars)
- Modify: `.env.example` (add all channel gateway vars + CF subdomain placeholders)
- Modify: `docs/dev-context.md` (add Cloudflare Tunnel architecture section)
- Delete content: remove ngrok mentions from `docs/` files

---

### Task 1: Add missing webhook URL env vars to docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Open docker-compose.yml and find the whatsapp-gateway service (around line 159)**

The current `whatsapp-gateway` environment block is:
```yaml
    environment:
      WHATSAPP_ACCESS_TOKEN: ${WHATSAPP_ACCESS_TOKEN}
      WHATSAPP_PHONE_NUMBER_ID: ${WHATSAPP_PHONE_NUMBER_ID}
      WHATSAPP_VERIFY_TOKEN: ${WHATSAPP_VERIFY_TOKEN}
      BACKEND_URL: http://backend:8000
```

**Step 2: Add `WHATSAPP_WEBHOOK_URL` to whatsapp-gateway**

Replace that block with:
```yaml
    environment:
      WHATSAPP_ACCESS_TOKEN: ${WHATSAPP_ACCESS_TOKEN}
      WHATSAPP_PHONE_NUMBER_ID: ${WHATSAPP_PHONE_NUMBER_ID}
      WHATSAPP_VERIFY_TOKEN: ${WHATSAPP_VERIFY_TOKEN}
      WHATSAPP_WEBHOOK_URL: ${WHATSAPP_WEBHOOK_URL}
      BACKEND_URL: http://backend:8000
```

**Step 3: Find the teams-gateway service (around line 176)**

The current `teams-gateway` environment block is:
```yaml
    environment:
      TEAMS_APP_ID: ${TEAMS_APP_ID}
      TEAMS_APP_PASSWORD: ${TEAMS_APP_PASSWORD}
      BACKEND_URL: http://backend:8000
```

**Step 4: Add `TEAMS_WEBHOOK_URL` to teams-gateway**

Replace that block with:
```yaml
    environment:
      TEAMS_APP_ID: ${TEAMS_APP_ID}
      TEAMS_APP_PASSWORD: ${TEAMS_APP_PASSWORD}
      TEAMS_WEBHOOK_URL: ${TEAMS_WEBHOOK_URL}
      BACKEND_URL: http://backend:8000
```

**Step 5: Verify the change is syntactically valid**

```bash
docker compose config --quiet && echo "VALID"
```
Expected: `VALID` (no YAML parse errors)

**Step 6: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(11-01): add WHATSAPP_WEBHOOK_URL and TEAMS_WEBHOOK_URL to gateway services"
```

---

### Task 2: Update .env.example with all channel gateway vars

**Files:**
- Modify: `.env.example`

**Step 1: Append channel gateway section to .env.example**

Add at the end of `.env.example`:
```bash
# ── Channel Gateways ──────────────────────────────────────────
# Telegram
TELEGRAM_BOT_TOKEN=CHANGE_ME
TELEGRAM_WEBHOOK_URL=https://telegram.CHANGE_YOUR_DOMAIN.com/webhook

# WhatsApp Business
WHATSAPP_ACCESS_TOKEN=CHANGE_ME
WHATSAPP_PHONE_NUMBER_ID=CHANGE_ME
WHATSAPP_VERIFY_TOKEN=CHANGE_ME
WHATSAPP_WEBHOOK_URL=https://whatsapp.CHANGE_YOUR_DOMAIN.com/webhook

# MS Teams
TEAMS_APP_ID=CHANGE_ME
TEAMS_APP_PASSWORD=CHANGE_ME
TEAMS_WEBHOOK_URL=https://teams.CHANGE_YOUR_DOMAIN.com/webhook

# Channel gateway backend URL (from host to backend — uses Tailscale IP)
GATEWAY_BACKEND_URL=http://100.68.144.118:8000
```

**Step 2: Commit**

```bash
git add .env.example
git commit -m "feat(11-01): add channel gateway env vars to .env.example"
```

---

### Task 3: Document Cloudflare Tunnel architecture in docs/dev-context.md

**Files:**
- Modify: `docs/dev-context.md`

**Step 1: Find the "Update Log" or end of the Channels section in dev-context.md**

Add a new section **before** the Update Log (or after the Channels API table). Insert:

```markdown
## Cloudflare Tunnel — Webhook Exposure

Channel webhooks (Telegram, WhatsApp, MS Teams) are exposed via a Cloudflare Tunnel running
on a remote LXC container. No `cloudflared` service runs locally.

**Topology:**
```
External platform (Telegram / WhatsApp / Teams)
         ↓ HTTPS
  Cloudflare (your domain)
         ↓
  cloudflared on LXC 172.16.155.118  ← always-on, managed separately
         ↓ Tailscale
  Workstation tailscale0: 100.68.144.118
         ↓
  Docker channel gateways
    :9001  telegram-gateway
    :9002  whatsapp-gateway
    :9003  teams-gateway
```

**LXC cloudflared config** (`/etc/cloudflared/config.yml` on the LXC):
```yaml
tunnel: <your-tunnel-id>
credentials-file: /etc/cloudflared/<your-tunnel-id>.json

ingress:
  - hostname: telegram.yourdomain.com
    service: http://100.68.144.118:9001
  - hostname: whatsapp.yourdomain.com
    service: http://100.68.144.118:9002
  - hostname: teams.yourdomain.com
    service: http://100.68.144.118:9003
  - service: http_status:404
```

**DNS records** (Cloudflare dashboard — one-time per subdomain):
- Type: CNAME
- Name: `telegram` (or `whatsapp`, `teams`)
- Target: `<tunnel-id>.cfargotunnel.com`
- Proxy: enabled (orange cloud)

**Webhook registration:**
- Telegram: set via `TELEGRAM_WEBHOOK_URL=https://telegram.yourdomain.com/webhook` — the
  telegram-gateway registers this URL with the BotFather API on startup
- WhatsApp: set `https://whatsapp.yourdomain.com/webhook` in Meta Business → Webhooks dashboard
- MS Teams: set `https://teams.yourdomain.com/webhook` in Azure Bot Service → Messaging endpoint

**Starting locally:** `docker compose up` — no extra steps. The LXC tunnel is always-on.
```

**Step 2: Commit**

```bash
git add docs/dev-context.md
git commit -m "docs(11-01): document Cloudflare Tunnel architecture and LXC config"
```

---

### Task 4: Remove ngrok references from docs

**Files:**
- Modify: `docs/dev-context.md` (remove any ngrok mentions)
- Modify: `.planning/research/PITFALLS.md` (update the Telegram webhook pitfall entry)
- Modify: `.planning/research/SUMMARY.md` (update the ngrok mention)

**Step 1: Search for remaining ngrok references in tracked files**

```bash
grep -rn "ngrok" . --include="*.md" --include="*.yml" --include="*.yaml" \
  --include="*.py" --include="*.env*" \
  | grep -v ".venv" | grep -v "__pycache__" | grep -v ".worktrees"
```

**Step 2: For each file containing "ngrok", replace the reference**

For `.planning/research/PITFALLS.md` (the Telegram webhook row), update the Fix column:
- Old: `use ngrok for dev, reverse proxy for production`
- New: `use Cloudflare Tunnel via remote LXC (see docs/dev-context.md)`

For `.planning/research/SUMMARY.md`:
- Old: `Telegram webhook URL (needs public HTTPS -- use ngrok for dev)`
- New: `Telegram webhook URL (needs public HTTPS — exposed via Cloudflare Tunnel on LXC)`

For any `05-02-PLAN.md` or `05-02-SUMMARY.md` references, those are archived history — leave them.

**Step 3: Verify no ngrok references remain in active docs**

```bash
grep -rn "ngrok" docs/ .planning/todos/ | grep -v ".worktrees"
```
Expected: zero results (or only historical phase plan files in `.planning/milestones/`)

**Step 4: Commit**

```bash
git add docs/ .planning/research/ .planning/todos/
git commit -m "docs(11-01): replace ngrok references with Cloudflare Tunnel in active docs"
```

---

### Task 5: Mark the pending todo as done

**Files:**
- Delete: `.planning/todos/pending/2026-03-02-replace-ngrok-with-cloudflare-tunnel-for-webhook-exposure.md`

**Step 1: Move todo to done**

```bash
mkdir -p .planning/todos/done
mv ".planning/todos/pending/2026-03-02-replace-ngrok-with-cloudflare-tunnel-for-webhook-exposure.md" \
   .planning/todos/done/
```

**Step 2: Commit**

```bash
git add .planning/todos/
git commit -m "chore(11-01): mark Cloudflare Tunnel todo as done"
```

---

### Task 6: Verify end-to-end (human step)

This task requires a live Telegram bot token and the LXC tunnel to be configured.

**Step 1: Ensure LXC has ingress rules configured** (as documented in Task 3)

SSH into the LXC (`ssh root@172.16.155.118`) and verify:
```bash
cloudflared tunnel info <tunnel-name>
# Should show 3 ingress routes
```

**Step 2: Start local services**

```bash
just up       # Docker infra
just backend  # FastAPI on :8000
docker compose up telegram-gateway -d
```

**Step 3: Send a test Telegram message to the bot**

The telegram-gateway registers its webhook on startup. Send a message to the bot and confirm:
- Telegram-gateway receives it (check `docker compose logs telegram-gateway`)
- Backend receives the forwarded request (check `just logs backend`)

**Step 4: Confirm no ngrok process is running**

```bash
ps aux | grep ngrok
```
Expected: no ngrok processes.
