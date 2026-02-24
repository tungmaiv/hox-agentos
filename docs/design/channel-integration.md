<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# let design channel integration with telegram, whatsapp, ms team and more architect must support extensible so we can add new channel in the furture

Design the channels as a **pluggable gateway layer**: one unified “Channel Gateway” service and per‑channel adapters that all speak the same internal interface.[^1][^2][^3]

***

## 1. High‑level architecture

- **Channel Gateway (core)**
    - Runs inside your FastAPI backend as a module (`backend/channels`).
    - Exposes a common API:
        - `receive_inbound_message(internal_channel_message)`
        - `send_outbound_message(user_id, channel, payload)`
    - Handles:
        - Identity mapping (Telegram ID → Blitz user).
        - Session routing (conversation IDs).
        - RBAC checks and throttling.
- **Channel Adapters (per platform)**
    - Telegram, WhatsApp, MS Teams, etc. implemented as pluggable adapters.
    - Each adapter converts platform‑specific events into the internal message format and vice versa.[^2][^4]
    - Can live:
        - In‑process with FastAPI (simple webhooks).
        - Or as small sidecar services calling a unified backend endpoint.

This mirrors OpenClaw’s “Gateway + Channels” pattern and Moltbot’s single control plane idea.[^3][^5][^1]

***

## 2. Internal message model (platform‑agnostic)

Define a canonical message type shared across adapters:

```python
# backend/channels/models.py
from pydantic import BaseModel
from enum import Enum

class ChannelType(str, Enum):
    telegram = "telegram"
    whatsapp = "whatsapp"
    ms_teams = "ms_teams"
    slack = "slack"
    web = "web"

class MessageDirection(str, Enum):
    inbound = "inbound"
    outbound = "outbound"

class InternalMessage(BaseModel):
    direction: MessageDirection
    channel: ChannelType
    external_user_id: str         # chat_id / phone / Teams user id
    external_chat_id: str | None  # group/channel/thread id
    user_id: str | None           # Blitz user id (after mapping)
    conversation_id: str | None   # internal conversation/session
    text: str | None
    attachments: list[dict] = []
    is_group: bool = False
    metadata: dict = {}
```

All adapters must implement a mapping from their webhooks/SDK events to `InternalMessage` and from `InternalMessage` to their send API.

***

## 3. Channel Gateway core

### 3.1 Interfaces

```python
# backend/channels/dispatcher.py
from .models import InternalMessage, ChannelType

class ChannelAdapter(Protocol):
    channel: ChannelType

    async def send(self, msg: InternalMessage) -> None:
        ...

class ChannelGateway:
    def __init__(self, adapters: dict[ChannelType, ChannelAdapter]):
        self.adapters = adapters

    async def handle_inbound(self, msg: InternalMessage):
        # 1. Resolve/attach Blitz user and conversation
        msg = await self._enrich_identity(msg)
        # 2. Apply allowlist/pairing rules if needed (like OpenClaw DM pairing)[web:86][web:88]
        if not await self._check_pairing(msg):
            return
        # 3. Route to agent runtime
        await self._route_to_agent(msg)

    async def send_outbound(self, msg: InternalMessage):
        adapter = self.adapters[msg.channel]
        await adapter.send(msg)
```

The gateway becomes the only entrypoint for all external messaging channels.[^5][^1][^3]

### 3.2 Identity mapping

Use a DB table:

```sql
CREATE TABLE channel_accounts (
  id             UUID PRIMARY KEY,
  user_id        UUID NOT NULL,
  channel        TEXT NOT NULL,      -- "telegram", "whatsapp", "ms_teams"
  external_user_id TEXT NOT NULL,    -- chat_id / phone / user id
  metadata       JSONB,
  created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE channel_sessions (
  id             UUID PRIMARY KEY,
  channel_account_id UUID NOT NULL REFERENCES channel_accounts(id),
  external_chat_id   TEXT,
  conversation_id    UUID NOT NULL,
  last_activity_at   TIMESTAMPTZ DEFAULT now()
);
```

`_enrich_identity(msg)`:

- Look up `ChannelAccount` by `(channel, external_user_id)`.
- If none:
    - Either create a pending pairing request (user must approve in the web UI or via admin).
    - Or create a guest user, depending on your policy.
- Then load/create `ChannelSession` by `(channel_account_id, external_chat_id)` and get `conversation_id` (AG‑UI thread id).

***

## 4. Telegram adapter

### 4.1 Transport choice

- For enterprise: use **webhooks** instead of polling:
    - Telegram will call `POST /channels/telegram/webhook` on your backend.[^6][^7]


### 4.2 Implementation

```python
# backend/channels/telegram_adapter.py
from .models import InternalMessage, ChannelType

class TelegramAdapter(ChannelAdapter):
    channel = ChannelType.telegram

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    async def send(self, msg: InternalMessage):
        # Only final messages to Telegram, no streaming chunks.[web:27][web:73]
        if not msg.text:
            return
        payload = {
            "chat_id": msg.external_chat_id or msg.external_user_id,
            "text": msg.text,
        }
        await httpx.post(f"{self.base_url}/sendMessage", json=payload)
```

Webhook route:

```python
# backend/api/routes/channels.py
@router.post("/channels/telegram/webhook")
async def telegram_webhook(update: dict, gateway: ChannelGateway = Depends(...)):
    # Extract chat/user ids + text
    msg = InternalMessage(
        direction="inbound",
        channel="telegram",
        external_user_id=str(update["message"]["from"]["id"]),
        external_chat_id=str(update["message"]["chat"]["id"]),
        text=update["message"].get("text"),
        is_group=update["message"]["chat"]["type"] in ("group", "supergroup"),
        metadata={"raw": update},
    )
    await gateway.handle_inbound(msg)
    return {"ok": True}
```

Telegram‑specific policies (e.g., “only respond when @mentioned in group chats”) live inside `_check_pairing` or metadata rules.

***

## 5. WhatsApp adapter

WhatsApp is trickier; most enterprise setups use:[^8][^4][^1]

- WhatsApp Business Cloud API, or
- A bridging library (Baileys‑like) running as a Node sidecar.


### 5.1 Sidecar service pattern

Implement a small Node or Python service:

```text
channel-gateways/whatsapp/
  app.ts  # listens to WhatsApp events, forwards to Blitz backend
```

- Receives WhatsApp messages.
- Posts them to `POST /channels/whatsapp/incoming` on your backend in `InternalMessage` format (JSON).
- Receives outbound messages via:
    - Backend calling a small “send” endpoint on the sidecar, or
    - Polling a queue.

FastAPI side:

```python
@router.post("/channels/whatsapp/incoming")
async def whatsapp_incoming(msg: InternalMessage, gateway: ChannelGateway = Depends(...)):
    await gateway.handle_inbound(msg)
    return {"ok": True}
```

Adapter:

```python
class WhatsAppAdapter(ChannelAdapter):
    channel = ChannelType.whatsapp

    def __init__(self, send_url: str, api_key: str):
        self.send_url = send_url
        self.api_key = api_key

    async def send(self, msg: InternalMessage):
        await httpx.post(
            self.send_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=msg.dict(),
        )
```

This keeps all channel‑specific logic isolated and allows you to swap underlying providers.

***

## 6. Microsoft Teams adapter

MS Teams integrates via the **Bot Framework / Graph API**.

### 6.1 Architecture

- Register a bot app in Azure AD.
- Expose a message endpoint that Bot Framework calls (e.g., `/channels/teams/webhook`).
- Use an SDK (python‑botbuilder) or call Graph API directly.

Simplified adapter:

```python
class TeamsAdapter(ChannelAdapter):
    channel = ChannelType.ms_teams

    def __init__(self, app_id: str, app_password: str):
        self.app_id = app_id
        self.app_password = app_password
        # init Bot Framework client or Graph client

    async def send(self, msg: InternalMessage):
        # Convert msg.text to Teams activity and send via SDK/Graph
        ...
```

Webhook route:

```python
@router.post("/channels/teams/webhook")
async def teams_webhook(activity: dict, gateway: ChannelGateway = Depends(...)):
    # Map activity to InternalMessage
    msg = InternalMessage(
        direction="inbound",
        channel="ms_teams",
        external_user_id=activity["from"]["id"],
        external_chat_id=activity["conversation"]["id"],
        text=activity.get("text"),
        is_group=activity["conversation"]["isGroup"],
        metadata={"raw": activity},
    )
    await gateway.handle_inbound(msg)
    return {}
```


***

## 7. Routing into Blitz AgentOS

`ChannelGateway._route_to_agent(msg)` does:

1. Build an AG‑UI session context:
    - `user_id` (from `ChannelAccount`).
    - `conversation_id` (from `ChannelSession`).
    - `channel` metadata (so the agent knows where it’s talking).
2. Call the same FastAPI Copilot Runtime endpoint as the web chat:
    - `POST /api/agents/chat` with:
        - `message = msg.text`.
        - `user_context` (roles, id).
        - `channel_context` (type, chat id).
3. When agent finishes:
    - Agent returns a message + optional A2UI content.
    - Backend maps it to `InternalMessage(direction="outbound", ...)`.
    - Passes to `gateway.send_outbound`.

For external messaging channels, follow OpenClaw’s rule: **send only final replies**, not streaming chunks; streaming stays in the internal UI.[^9][^1][^2]

***

## 8. Extensibility for future channels

To add a new channel (e.g., Discord, Line, Zalo):

1. Implement `ChannelAdapter` with:
    - Constructor receiving config (`token`, `webhook_url`, etc.).
    - `send` method.
2. Create an inbound route (webhook) or small sidecar:
    - Convert platform payload to `InternalMessage(direction="inbound", ...)`.
    - Call `gateway.handle_inbound`.
3. Register adapter:
```python
adapters = {
  ChannelType.telegram: TelegramAdapter(...),
  ChannelType.whatsapp: WhatsAppAdapter(...),
  ChannelType.ms_teams: TeamsAdapter(...),
  # new:
  ChannelType.discord: DiscordAdapter(...),
}
gateway = ChannelGateway(adapters)
```

4. Add config:
```yaml
channels:
  telegram:
    enabled: true
    bot_token: ...
  whatsapp:
    enabled: true
    gateway_url: ...
  ms_teams:
    enabled: true
    app_id: ...
    app_password: ...
  discord:
    enabled: true
    bot_token: ...
```

5. Update `ChannelType` enum and any admin UI for enable/disable toggles.

This gives you an **OpenClaw‑style multi‑channel hub** where adding Telegram, WhatsApp, Teams, or any future platform is just implementing a new adapter and binding routes, without touching the core agent stack.[^10][^1][^2]
<span style="display:none">[^11][^12][^13][^14][^15][^16][^17][^18][^19][^20][^21][^22][^23][^24][^25][^26][^27][^28][^29][^30]</span>

<div align="center">⁂</div>

[^1]: https://github.com/openclaw/openclaw/blob/main/README.md

[^2]: https://eastondev.com/blog/en/posts/ai/20260205-openclaw-architecture-guide/

[^3]: https://lumadock.com/tutorials/moltbot-multi-channel-setup

[^4]: https://amiable.dev/blog/luminescent-cluster/05-multi-platform-chatbots/

[^5]: https://openclaw-ai.online/architecture/

[^6]: https://yandex.cloud/en/docs/tutorials/serverless/telegram-ai-bot-workflows

[^7]: https://yandex.cloud/en/docs/foundation-models/tutorials/telegram-ai-bot-workflows

[^8]: https://openclaw-ai.online/channels/

[^9]: https://github.com/openclaw/openclaw/blob/main/AGENTS.md

[^10]: https://vallettasoftware.com/blog/post/openclaw-2026-guide

[^11]: https://github.com/openclaw/openclaw/pull/9201

[^12]: https://github.com/openclaw/openclaw/pull/9939

[^13]: https://github.com/openclaw/openclaw/issues/7880

[^14]: https://github.com/openclaw/openclaw/discussions/6020

[^15]: https://github.com/openclaw/openclaw/issues/5717

[^16]: https://github.com/openclaw/openclaw/blob/main/docs/pi.md

[^17]: https://github.com/openclaw/openclaw/issues/4942

[^18]: https://github.com/openclaw/openclaw/blob/main/CHANGELOG.md

[^19]: https://github.com/openclaw/openclaw/issues/5250

[^20]: https://github.com/openclaw/openclaw/issues/17817

[^21]: https://github.com/openclaw/openclaw/discussions/17859

[^22]: https://github.com/openclaw/openclaw/issues/22932

[^23]: https://github.com/openclaw/openclaw/issues/15451

[^24]: https://ppaolo.substack.com/p/openclaw-system-architecture-overview

[^25]: https://www.linkedin.com/pulse/quick-summary-clawdbot-openclaws-architecture-elaheh-ahmadi-clrgc

[^26]: https://binds.ch/blog/openclaw-systems-analysis

[^27]: https://stackoverflow.com/questions/54671750/multiple-slack-channel-support-for-botframework

[^28]: https://lobehub.com/mcp/pandoll-ai-telegram-gateway

[^29]: https://docs.openclaw.ai/channels

[^30]: https://dev.to/onin/one-openclaw-gateway-multiple-isolated-ai-assistants-one-telegram-bot-per-worker-3k97

