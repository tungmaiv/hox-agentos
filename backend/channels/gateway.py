"""
ChannelGateway -- central dispatcher for all channel inbound/outbound traffic.

Responsibilities:
  1. Pairing command detection and processing (/pair <code>)
  2. Identity mapping: (channel, external_user_id) -> ChannelAccount -> user_id
  3. Session resolution: (channel_account, external_chat_id) -> ChannelSession -> conversation_id
  4. Agent invocation: reuse master agent's run_conversation (same as web chat)
  5. Outbound delivery: POST to the appropriate sidecar's /send endpoint

Security: /api/channels/incoming is internal-only (Docker network isolation).
All agent invocations pass through the same 3-gate security (user_id from channel_account).
"""
import asyncio
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import structlog
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from channels.models import InternalMessage
from core.logging import timed
from core.models.channel import ChannelAccount, ChannelSession

logger = structlog.get_logger(__name__)

_PAIRING_CODE_LENGTH = 6
_PAIRING_EXPIRY_MINUTES = 10

# Module-level LangGraph checkpointer registry.
# Keyed by str(conversation_id) — reused across _invoke_agent() calls for the same session.
# Entries persist for the lifetime of the process (acceptable at single-node MVP scale).
_channel_graph_savers: dict[str, MemorySaver] = {}


# ── Module-level formatters (reusable from node_handlers without a gateway instance) ──


def format_for_channel(text: str) -> str:
    """Convert structured JSON sub-agent output to human-readable text for channels.

    Importable as a standalone function — no ChannelGateway instance required.
    Used by both ChannelGateway._invoke_agent and agents.node_handlers._handle_agent_node.
    """
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text  # Not JSON — already human-readable

    agent = data.get("agent")
    if agent == "calendar":
        return _format_calendar(data)
    if agent == "email":
        return _format_email(data)
    if agent == "project":
        return _format_project(data)
    return text  # Unknown agent JSON — send as-is


def _format_calendar(data: dict[str, Any]) -> str:
    date_str = data.get("date", "today")
    events = data.get("events", [])
    if not events:
        return f"No events on your calendar for {date_str}."
    lines = [f"Your calendar for {date_str}:\n"]
    for e in events:
        start = e.get("start_time", "")
        # Extract HH:MM from ISO timestamp
        time_str = start[11:16] if len(start) >= 16 else start
        location = e.get("location", "")
        conflict = " (CONFLICT)" if e.get("has_conflict") else ""
        loc_part = f" — {location}" if location else ""
        lines.append(f"• {time_str}  {e.get('title', 'Untitled')}{loc_part}{conflict}")
    return "\n".join(lines)


def _format_email(data: dict[str, Any]) -> str:
    unread = data.get("unread_count", 0)
    items = data.get("items", [])
    if not items:
        return "No emails to show."
    total = len(items)
    lines = [f"You have {total} email(s) ({unread} unread):\n"]
    for item in items:
        flag = "[NEW] " if item.get("is_unread") else ""
        lines.append(f"• {flag}{item.get('from_', 'Unknown')}: {item.get('subject', '(no subject)')}")
        snippet = item.get("snippet", "")
        if snippet:
            lines.append(f"  {snippet[:100]}")
    return "\n".join(lines)


def _format_project(data: dict[str, Any]) -> str:
    name = data.get("project_name", "Unknown")
    status = data.get("status", "unknown")
    progress = data.get("progress_pct", 0)
    owner = data.get("owner", "")
    last_update = data.get("last_update", "")
    lines = [
        f"Project: {name}",
        f"Status: {status} — {progress}% complete",
    ]
    if owner:
        lines.append(f"Owner: {owner}")
    if last_update:
        lines.append(f"Last update: {last_update}")
    return "\n".join(lines)


class ChannelGateway:
    def __init__(self, sidecar_urls: dict[str, str]) -> None:
        self.sidecar_urls = sidecar_urls

    # -- Public API ---------------------------------------------------------

    def register_adapter(self, name: str, adapter: object) -> None:
        """Register a Python-level ChannelAdapter implementation.

        Validates that adapter satisfies the ChannelAdapter protocol at registration
        time. Raises TypeError immediately if the object does not conform.

        The sidecar_urls mechanism is separate and unchanged — this method is for
        future Python-level adapter registration only.

        Args:
            name: Channel identifier (e.g. "telegram", "whatsapp")
            adapter: Object implementing async def send(msg: InternalMessage) -> None

        Raises:
            TypeError: If adapter does not satisfy ChannelAdapter protocol.
        """
        from channels.adapter import ChannelAdapter

        if not isinstance(adapter, ChannelAdapter):
            raise TypeError(
                f"register_adapter({name!r}): adapter must implement ChannelAdapter protocol "
                f"(requires 'async def send(msg: InternalMessage) -> None'), "
                f"got {type(adapter).__name__!r}"
            )
        logger.info("channel_adapter_registered", name=name, adapter_type=type(adapter).__name__)

    def is_pairing_command(self, msg: InternalMessage) -> bool:
        """Check if the message is a /pair command."""
        return bool(msg.text and msg.text.strip().startswith("/pair "))

    async def resolve_account(
        self, msg: InternalMessage, db: AsyncSession
    ) -> ChannelAccount | None:
        """Look up a ChannelAccount by (channel, external_user_id)."""
        result = await db.execute(
            select(ChannelAccount).where(
                and_(
                    ChannelAccount.channel == msg.channel,
                    ChannelAccount.external_user_id == msg.external_user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def resolve_or_create_session(
        self,
        account: ChannelAccount,
        msg: InternalMessage,
        db: AsyncSession,
    ) -> ChannelSession:
        """Find or create a ChannelSession for this chat."""
        chat_id = msg.external_chat_id or msg.external_user_id
        result = await db.execute(
            select(ChannelSession).where(
                and_(
                    ChannelSession.channel_account_id == account.id,
                    ChannelSession.external_chat_id == chat_id,
                )
            )
        )
        session = result.scalar_one_or_none()
        if session:
            session.last_activity_at = datetime.now(timezone.utc)
            await db.commit()
            return session

        new_session = ChannelSession(
            id=uuid.uuid4(),
            channel_account_id=account.id,
            external_chat_id=chat_id,
            conversation_id=uuid.uuid4(),
        )
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
        return new_session

    async def generate_pairing_code(
        self, user_id: uuid.UUID, channel: str, db: AsyncSession
    ) -> str:
        """Generate a 6-character alphanumeric pairing code for the user."""
        code = secrets.token_hex(3).upper()[:_PAIRING_CODE_LENGTH]
        expires = datetime.now(timezone.utc) + timedelta(minutes=_PAIRING_EXPIRY_MINUTES)

        # Upsert: if a pending (unpaired) account for this user+channel exists, update it
        result = await db.execute(
            select(ChannelAccount).where(
                and_(
                    ChannelAccount.user_id == user_id,
                    ChannelAccount.channel == channel,
                    ChannelAccount.is_paired == False,  # noqa: E712
                )
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.pairing_code = code
            existing.pairing_expires = expires
        else:
            acct = ChannelAccount(
                id=uuid.uuid4(),
                user_id=user_id,
                channel=channel,
                external_user_id="",  # filled on pairing
                pairing_code=code,
                pairing_expires=expires,
                is_paired=False,
            )
            db.add(acct)
        await db.commit()

        logger.info("pairing_code_generated", user_id=str(user_id), channel=channel)
        return code

    async def handle_pairing(
        self, msg: InternalMessage, db: AsyncSession
    ) -> InternalMessage:
        """Process a /pair <code> command. Returns an outbound response message."""
        parts = (msg.text or "").strip().split()
        code = parts[1] if len(parts) >= 2 else ""

        result = await db.execute(
            select(ChannelAccount).where(
                and_(
                    ChannelAccount.pairing_code == code,
                    ChannelAccount.channel == msg.channel,
                    ChannelAccount.is_paired == False,  # noqa: E712
                )
            )
        )
        acct = result.scalar_one_or_none()

        if not acct:
            return self._make_reply(
                msg, "Invalid or expired pairing code. Please generate a new code in Settings."
            )

        now = datetime.now(timezone.utc)
        # SQLite returns offset-naive datetimes; PostgreSQL returns offset-aware.
        # Normalize to UTC-aware for safe comparison.
        expires = acct.pairing_expires
        if expires and expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires and expires < now:
            return self._make_reply(
                msg, "Pairing code has expired. Please generate a new code in Settings."
            )

        # Link the account
        acct.external_user_id = msg.external_user_id
        acct.is_paired = True
        acct.pairing_code = None
        acct.pairing_expires = None
        acct.display_name = msg.metadata.get("display_name")
        await db.commit()

        logger.info(
            "channel_paired",
            user_id=str(acct.user_id),
            channel=msg.channel,
            external_user_id=msg.external_user_id,
        )
        return self._make_reply(
            msg,
            "Account linked successfully! You can now chat with Blitz here.",
        )

    async def handle_inbound(
        self, msg: InternalMessage, db: AsyncSession
    ) -> InternalMessage:
        """
        Main entry point for all inbound channel messages.

        1. Check for pairing command
        2. Resolve identity
        3. Resolve session
        4. Invoke agent (placeholder -- wired in 05-05)
        5. Send outbound response
        """
        if self.is_pairing_command(msg):
            response = await self.handle_pairing(msg, db)
            await self.send_outbound(response)
            return response

        account = await self.resolve_account(msg, db)
        if not account or not account.is_paired:
            response = self._make_reply(
                msg,
                "Please link your account first. Visit Settings > Channel Linking in the Blitz web app.",
            )
            await self.send_outbound(response)
            return response

        msg.user_id = account.user_id
        session = await self.resolve_or_create_session(account, msg, db)
        msg.conversation_id = session.conversation_id

        # Agent invocation — delivers directly via delivery_router_node -> send_outbound()
        await self._invoke_agent(msg)
        # Return a placeholder for callers that inspect the return value
        return self._make_reply(msg, "")

    async def send_outbound(self, msg: InternalMessage) -> None:
        """Send an outbound message to the appropriate channel sidecar."""
        if msg.channel == "web":
            logger.debug("outbound_web_skip", note="Web delivery handled by AG-UI")
            return

        url = self.sidecar_urls.get(msg.channel)
        if not url:
            logger.warning("outbound_no_sidecar", channel=msg.channel)
            return

        send_url = f"{url}/send"
        backoff_delays = [1.0, 2.0, 4.0]

        for attempt, delay in enumerate(backoff_delays, start=1):
            try:
                user_id_str = str(msg.user_id) if msg.user_id else ""
                with timed(logger, "channel_delivery", channel=msg.channel, user_id=user_id_str):
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post(
                            send_url,
                            json=msg.model_dump(mode="json"),
                        )
                        resp.raise_for_status()
                logger.info(
                    "outbound_sent",
                    channel=msg.channel,
                    external_user_id=msg.external_user_id,
                )
                return
            except httpx.HTTPError as exc:
                if attempt < len(backoff_delays):
                    logger.warning(
                        "outbound_send_retry",
                        channel=msg.channel,
                        attempt=attempt,
                        error=str(exc),
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "outbound_send_failed",
                        channel=msg.channel,
                        error=str(exc),
                        attempts=attempt,
                    )

    # -- Private helpers ----------------------------------------------------

    async def _invoke_agent(self, msg: InternalMessage) -> None:
        """
        Invoke the master agent for a channel message.

        Uses the same LangGraph master graph as web chat. Reuses a MemorySaver
        keyed by conversation_id for multi-turn continuity within a session.
        Sets delivery_targets to the inbound channel so delivery_router_node
        delivers the response directly — no response text extraction needed.

        Security: user_id comes from ChannelAccount (resolved from channel_accounts
        table), never from request body. All gates apply identically to web chat.

        Timeout: 60 seconds per locked decision.
        """
        from agents.master_agent import create_master_graph
        from core.context import current_conversation_id_ctx, current_user_ctx
        from security.keycloak_client import fetch_user_realm_roles

        logger.info(
            "channel_agent_invoke",
            channel=msg.channel,
            user_id=str(msg.user_id),
        )

        # Fetch fresh roles from Keycloak (security-first: no stale/hardcoded roles)
        try:
            roles = await fetch_user_realm_roles(str(msg.user_id))
        except Exception as exc:
            logger.error(
                "channel_agent_roles_failed",
                channel=msg.channel,
                user_id=str(msg.user_id),
                error=str(exc),
            )
            error_reply = self._make_reply(
                msg, "Sorry, I couldn't verify your permissions. Please try again later."
            )
            await self.send_outbound(error_reply)
            return

        # Build a minimal UserContext for contextvar injection
        user_context = {
            "user_id": msg.user_id,
            "email": "",
            "username": "",
            "roles": roles,
            "groups": [],
        }

        # Set contextvars so graph nodes (load_memory, save_memory) can find user/conversation
        user_token = current_user_ctx.set(user_context)
        conv_token = (
            current_conversation_id_ctx.set(msg.conversation_id)
            if msg.conversation_id
            else None
        )

        try:
            # Reuse or create a MemorySaver for this conversation_id (multi-turn continuity)
            saver_key = str(msg.conversation_id or uuid.uuid4())
            if saver_key not in _channel_graph_savers:
                _channel_graph_savers[saver_key] = MemorySaver()
            saver = _channel_graph_savers[saver_key]

            graph = create_master_graph(checkpointer=saver)

            # Set delivery_targets so delivery_router_node routes to the correct channel.
            # user_id must be in state so delivery_router_node can resolve the channel account.
            initial_state = {
                "messages": [HumanMessage(content=msg.text or "")],
                "delivery_targets": [msg.channel.upper()],
                "user_id": msg.user_id,
            }
            config = {"configurable": {"thread_id": saver_key}}

            await asyncio.wait_for(
                graph.ainvoke(initial_state, config=config),
                timeout=60.0,
            )
            # Response delivered directly by delivery_router_node via send_outbound()

        except asyncio.TimeoutError:
            logger.error("channel_agent_timeout", channel=msg.channel, user_id=str(msg.user_id))
            error_reply = self._make_reply(
                msg, "Sorry, I couldn't process your request. Please try again."
            )
            await self.send_outbound(error_reply)
        except Exception as exc:
            logger.error("channel_agent_error", channel=msg.channel, error=str(exc))
            error_reply = self._make_reply(
                msg, "Sorry, I couldn't process your request. Please try again."
            )
            await self.send_outbound(error_reply)
        finally:
            current_user_ctx.reset(user_token)
            if conv_token is not None:
                current_conversation_id_ctx.reset(conv_token)

    def _format_for_channel(self, text: str) -> str:
        """Delegate to module-level format_for_channel (backward compat)."""
        return format_for_channel(text)

    def _format_calendar(self, data: dict[str, Any]) -> str:
        return _format_calendar(data)

    def _format_email(self, data: dict[str, Any]) -> str:
        return _format_email(data)

    def _format_project(self, data: dict[str, Any]) -> str:
        return _format_project(data)

    def _make_reply(self, original: InternalMessage, text: str) -> InternalMessage:
        """Create an outbound reply to an inbound message."""
        return InternalMessage(
            direction="outbound",
            channel=original.channel,
            external_user_id=original.external_user_id,
            external_chat_id=original.external_chat_id,
            user_id=original.user_id,
            conversation_id=original.conversation_id,
            text=text,
        )
