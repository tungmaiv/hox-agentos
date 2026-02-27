# Phase 5: Multi-Channel Integration — Design

> **Date:** 2026-02-28
> **Phase:** 5 (Scheduler and Channels)
> **Status:** Approved
> **Scope:** Telegram + WhatsApp Cloud API + MS Teams with sidecar service architecture

---

## 1. Overview

Phase 5 adds multi-channel messaging to Blitz AgentOS. Users can interact with the master agent from Telegram, WhatsApp, and MS Teams with the same capabilities as web chat. Each channel runs as an isolated Docker sidecar service.

**Key decisions from brainstorming:**
- Architecture: Sidecar services (one Docker container per channel)
- Identity pairing: 6-digit code generated in web UI, sent to bot
- WhatsApp: Official Cloud API (not Baileys)
- Rich content: Text + Markdown + inline buttons (Telegram InlineKeyboard, WhatsApp Interactive, Teams Adaptive Cards)

---

## 2. Architecture

```
                    External Platforms
                    ┌──────┐ ┌──────┐ ┌──────┐
                    │ TG   │ │ WA   │ │Teams │
                    │Webook│ │Cloud │ │Bot FW│
                    └──┬───┘ └──┬───┘ └──┬───┘
                       │        │        │
         ┌─────────────▼────────▼────────▼──────────────┐
         │         SIDECAR DOCKER SERVICES               │
         │  ┌──────────┐ ┌──────────┐ ┌──────────┐     │
         │  │ telegram  │ │ whatsapp │ │  teams   │     │
         │  │ :9001     │ │ :9002    │ │ :9003    │     │
         │  │ FastAPI   │ │ FastAPI  │ │ FastAPI  │     │
         │  │ /webhook  │ │ /webhook │ │ /webhook │     │
         │  │ /send     │ │ /send    │ │ /send    │     │
         │  └─────┬─────┘ └────┬─────┘ └────┬─────┘     │
         └────────┼────────────┼─────────────┼───────────┘
                  │            │             │
                  │ InternalMessage (JSON)   │
                  └────────────┼─────────────┘
                               ▼
         ┌─────────────────────────────────────────────┐
         │              BACKEND (FastAPI :8000)         │
         │                                             │
         │  POST /api/channels/incoming                │
         │       ▼                                     │
         │  ChannelGateway.handle_inbound()            │
         │    1. Pairing command detection             │
         │    2. Identity mapping (channel_accounts)   │
         │    3. Session resolution (channel_sessions)  │
         │    4. Route to master agent                 │
         │       ▼                                     │
         │  Master Agent (same as web chat)            │
         │       ▼                                     │
         │  ChannelGateway.send_outbound()             │
         │    → POST http://telegram-gateway:9001/send │
         │    → POST http://whatsapp-gateway:9002/send │
         │    → POST http://teams-gateway:9003/send    │
         └─────────────────────────────────────────────┘
```

Each sidecar is a minimal FastAPI service:
- `/webhook` — receives platform events, translates to InternalMessage, forwards to backend
- `/send` — receives InternalMessage from backend, translates to platform API calls

Backend owns all business logic: identity mapping, agent routing, security (Gate 1-3).

---

## 3. Data Models

### 3.1 Database Tables (Alembic migration 012)

```sql
CREATE TABLE channel_accounts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID,                    -- NULL until paired
    channel          TEXT NOT NULL,           -- "telegram", "whatsapp", "ms_teams"
    external_user_id TEXT NOT NULL,           -- telegram chat_id / phone / teams user id
    display_name     TEXT,                    -- platform display name
    pairing_code     TEXT,                    -- 6-digit code (NULL after paired)
    pairing_expires  TIMESTAMPTZ,            -- code expiry (10 min)
    is_paired        BOOLEAN NOT NULL DEFAULT FALSE,
    metadata         JSONB DEFAULT '{}',
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now(),
    UNIQUE (channel, external_user_id)
);

CREATE TABLE channel_sessions (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_account_id UUID NOT NULL REFERENCES channel_accounts(id),
    external_chat_id   TEXT NOT NULL,         -- group/thread id or DM id
    conversation_id    UUID NOT NULL,         -- Blitz internal conversation ID
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    last_activity_at   TIMESTAMPTZ DEFAULT now(),
    created_at         TIMESTAMPTZ DEFAULT now(),
    UNIQUE (channel_account_id, external_chat_id)
);
```

No FK on `user_id` — users live in Keycloak (same pattern as existing tables).

### 3.2 InternalMessage (Pydantic model)

```python
# backend/channels/models.py

class MessageAction(BaseModel):
    label: str                                           # button text
    action_id: str                                       # callback data
    style: Literal["primary", "secondary", "danger"] = "primary"

class Attachment(BaseModel):
    type: Literal["image", "file", "audio", "video"]
    url: str | None = None
    file_path: str | None = None
    mime_type: str | None = None

class InternalMessage(BaseModel):
    direction: Literal["inbound", "outbound"]
    channel: Literal["telegram", "whatsapp", "ms_teams", "web"]
    external_user_id: str
    external_chat_id: str | None = None
    user_id: UUID | None = None                          # filled after identity mapping
    conversation_id: UUID | None = None                  # filled after session resolution
    text: str | None = None
    attachments: list[Attachment] = []
    actions: list[MessageAction] = []                    # inline buttons
    is_group: bool = False
    metadata: dict = {}
```

---

## 4. Identity Pairing Flow

```
1. User opens Blitz web UI → Settings → Channel Linking
2. Clicks "Link Telegram" → POST /api/channels/pair {channel: "telegram"}
3. Backend generates 6-digit code, creates/updates channel_account:
   - pairing_code = "ABC123"
   - pairing_expires = now() + 10 minutes
   - is_paired = False
4. Frontend shows: "Send /pair ABC123 to @BlitzBot on Telegram"
5. User sends "/pair ABC123" to Telegram bot
6. Telegram sidecar → POST /api/channels/incoming with InternalMessage
7. ChannelGateway detects /pair command:
   a. Finds channel_account WHERE pairing_code = 'ABC123'
      AND pairing_expires > now() AND channel = 'telegram'
   b. Sets external_user_id, user_id, is_paired = True
   c. Clears pairing_code + pairing_expires
   d. Sends response: "Account linked successfully! You can now chat with Blitz."
8. Unpaired users get: "Please link your account at https://blitz.local/settings"
```

---

## 5. Channel Sidecar Designs

### 5.1 Telegram Sidecar (channel-gateways/telegram/)

```
channel-gateways/telegram/
├── Dockerfile
├── pyproject.toml               # fastapi, httpx, uvicorn
├── main.py                      # FastAPI app with /webhook + /send + /health
└── telegram_api.py              # Telegram Bot API wrapper
```

**Inbound** (`POST /webhook`):
- Receives Telegram Update JSON (message or callback_query)
- Extracts from.id, chat.id, text
- Callback queries → InternalMessage with metadata.callback_data
- Forwards InternalMessage to backend /api/channels/incoming

**Outbound** (`POST /send`):
- If `actions` present: builds InlineKeyboardMarkup
- parse_mode=MarkdownV2 for text formatting
- Calls Telegram Bot API sendMessage

**Webhook registration:** On startup, calls setWebhook with the sidecar's external URL.

### 5.2 WhatsApp Sidecar (channel-gateways/whatsapp/)

```
channel-gateways/whatsapp/
├── Dockerfile
├── pyproject.toml
├── main.py                      # FastAPI app
└── whatsapp_api.py              # WhatsApp Cloud API wrapper
```

**Inbound**:
- `GET /webhook` — verification challenge (hub.verify_token)
- `POST /webhook` — message events from WhatsApp Cloud API
- Extracts from (phone), wa_id, text.body
- Forwards InternalMessage to backend

**Outbound** (`POST /send`):
- If `actions`: Interactive message with buttons (max 3 per WhatsApp rules)
- If text: plain text message
- API: POST https://graph.facebook.com/v21.0/{phone_number_id}/messages

### 5.3 MS Teams Sidecar (channel-gateways/teams/)

```
channel-gateways/teams/
├── Dockerfile
├── pyproject.toml               # fastapi, botbuilder-core, botbuilder-integration-aiohttp
├── main.py                      # FastAPI app
└── teams_api.py                 # Bot Framework wrapper
```

**Inbound** (`POST /webhook`):
- Receives Bot Framework Activity JSON
- Token validation via Bot Framework authentication
- Extracts from.id, conversation.id, text

**Outbound** (`POST /send`):
- If `actions`: Adaptive Card with Action.Submit buttons
- If text: plain text Activity
- Uses ConnectorClient to reply

---

## 6. Backend Gateway

### 6.1 ChannelGateway

```python
# backend/channels/gateway.py

class ChannelGateway:
    async def handle_inbound(self, msg: InternalMessage, db: AsyncSession) -> InternalMessage:
        if self._is_pairing_command(msg):
            return await self._handle_pairing(msg, db)

        account = await self._resolve_account(msg, db)
        if not account or not account.is_paired:
            return self._unpaired_response(msg)

        msg.user_id = account.user_id
        session = await self._resolve_session(account, msg, db)
        msg.conversation_id = session.conversation_id

        response = await self._invoke_agent(msg)
        await self.send_outbound(response)
        return response

    async def send_outbound(self, msg: InternalMessage) -> None:
        sidecar_url = SIDECAR_URLS[msg.channel]
        async with httpx.AsyncClient() as client:
            await client.post(f"{sidecar_url}/send", json=msg.model_dump(mode="json"))
```

### 6.2 Agent Integration

Channel messages reuse the same master agent as web chat. Differences:
- `BlitzState.channel` = "telegram" / "whatsapp" / "ms_teams"
- Response collected as single message (no SSE streaming)
- Response goes through send_outbound() instead of AG-UI

### 6.3 Channel Output Node Handler

For canvas workflows with channel_output_node:
- Reads channel + template/message from node config
- Resolves user's channel_account for the target channel
- Sends via ChannelGateway.send_outbound()

### 6.4 Backend Routes

```
POST /api/channels/incoming          — receives InternalMessage from sidecars (no auth — internal only)
POST /api/channels/pair              — generate pairing code (requires JWT)
GET  /api/channels/accounts          — list user's linked accounts (requires JWT)
DELETE /api/channels/accounts/{id}   — unlink account (requires JWT)
```

Security: `/api/channels/incoming` is internal-only (sidecars call it). Protected by Docker network isolation — not exposed to host.

---

## 7. Frontend Changes

### Settings Page — Channel Linking

Add to `/settings` page:
- List of paired channel accounts with unlink button
- "Link Telegram" / "Link WhatsApp" / "Link Teams" buttons
- Each generates pairing code with 10-minute countdown
- Copy-paste instructions for each platform

---

## 8. Testing Strategy

**Backend unit tests:**
- `test_channel_gateway.py` — identity mapping, session resolution, pairing
- `test_internal_message.py` — serialization, validation
- `test_channel_output_node.py` — node handler with mock gateway
- `test_pairing.py` — code generation, expiry, success/failure paths

**Backend integration tests:**
- `test_channel_routes.py` — API routes with mock DB and mock sidecar

**Sidecar tests (per sidecar):**
- `test_telegram_webhook.py` — Update → InternalMessage
- `test_telegram_send.py` — InternalMessage → sendMessage + InlineKeyboard
- Same for WhatsApp and Teams

---

## 9. Plan Breakdown

| Plan | Scope | Key Deliverables |
|------|-------|-----------------|
| **05-01** | Core: DB models, InternalMessage, ChannelGateway, pairing, backend routes | Alembic migration 012, channel models, gateway.py, routes/channels.py, tests |
| **05-02** | Telegram sidecar | Dockerfile, main.py, telegram_api.py, Docker Compose, tests |
| **05-03** | WhatsApp sidecar | Dockerfile, main.py, whatsapp_api.py, Docker Compose, tests |
| **05-04** | MS Teams sidecar | Dockerfile, main.py, teams_api.py, Docker Compose, tests |
| **05-05** | Integration: channel_output_node handler, delivery_router wiring, frontend settings page | node_handlers update, delivery_router update, settings UI, tests |

Plans 02-04 depend on 01 (shared InternalMessage model). Plans 02-04 can be parallelized.
Plan 05 depends on 01 + at least one of 02-04 for end-to-end testing.

---

## 10. Success Criteria (from ROADMAP.md)

1. User can send a message to the Blitz Telegram bot and receive agent responses with full tool access
2. User can interact with the agent via WhatsApp Business and receive the same capabilities as web chat
3. User can interact with the agent via MS Teams with the same capabilities as web chat
4. External platform user IDs mapped to Blitz user IDs via channel_accounts table — unlinked users receive a pairing prompt
5. New channel adapters can be added by implementing the ChannelAdapter protocol without modifying agent, tool, or memory code
