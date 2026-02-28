"""
DeliveryRouterNode -- deterministic output routing at end of master agent graph.
NOT a sub-agent (no LLM calls). Routes formatted response to delivery target(s).

Per CONTEXT.md decision:
- WEB_CHAT: active in Phase 3 (CopilotKit handles this automatically via AG-UI)
- EMAIL_NOTIFY: stub -- log warning + no-op (email notifications not in MVP)
- TELEGRAM, WHATSAPP, TEAMS: real delivery via ChannelGateway.send_outbound()

This is distinct from Phase 5 ChannelAdapter (inbound):
- DeliveryRouterNode = outbound (Phase 3+5)
- ChannelAdapter = inbound (Phase 5)

BlitzState.delivery_targets defaults to [DeliveryTarget.WEB_CHAT] (set in 03-02).
"""
from enum import Enum
from typing import Any
from uuid import UUID

import structlog

from agents.state.types import BlitzState

logger = structlog.get_logger(__name__)


async def _resolve_channel_account(
    user_id: UUID, channel: str
) -> tuple[str, str | None]:
    """Resolve external_user_id and external_chat_id from channel_accounts.

    Returns (external_user_id, external_chat_id) or ("", None) if not found.
    For DMs, external_chat_id == external_user_id.
    """
    from core.db import async_session
    from core.models.channel import ChannelAccount
    from sqlalchemy import and_, select

    async with async_session() as session:
        result = await session.execute(
            select(ChannelAccount).where(
                and_(
                    ChannelAccount.user_id == user_id,
                    ChannelAccount.channel == channel,
                    ChannelAccount.is_paired == True,  # noqa: E712
                )
            )
        )
        account = result.scalar_one_or_none()
        if account:
            return account.external_user_id, account.external_user_id
    return "", None


class DeliveryTarget(str, Enum):
    WEB_CHAT = "WEB_CHAT"
    EMAIL_NOTIFY = "EMAIL_NOTIFY"
    TELEGRAM = "TELEGRAM"
    WHATSAPP = "WHATSAPP"
    TEAMS = "TEAMS"


def _get_gateway():
    """Return the singleton ChannelGateway from the channels route module."""
    from api.routes.channels import get_channel_gateway
    return get_channel_gateway()


async def deliver(target: DeliveryTarget, payload: Any, user_id: UUID | None = None) -> None:
    """
    Route payload to the specified delivery target.

    WEB_CHAT: handled by CopilotKit/AG-UI automatically -- no action needed.
    TELEGRAM, WHATSAPP, TEAMS: real outbound via ChannelGateway.send_outbound().
      Requires user_id to resolve the linked channel account for external_chat_id.
    EMAIL_NOTIFY: stub (not in MVP scope).
    """
    if target == DeliveryTarget.WEB_CHAT:
        # WEB_CHAT delivery is handled by CopilotKit/AG-UI automatically.
        # No additional action needed here.
        logger.debug("delivery_web_chat", payload_type=type(payload).__name__)

    elif target == DeliveryTarget.EMAIL_NOTIFY:
        logger.warning(
            "delivery_target_stub_not_implemented",
            target=target.value,
            note="Email notification delivery not in MVP scope",
        )

    elif target in (DeliveryTarget.TELEGRAM, DeliveryTarget.WHATSAPP, DeliveryTarget.TEAMS):
        from channels.models import InternalMessage

        channel_map = {
            DeliveryTarget.TELEGRAM: "telegram",
            DeliveryTarget.WHATSAPP: "whatsapp",
            DeliveryTarget.TEAMS: "ms_teams",
        }
        channel = channel_map[target]
        gateway = _get_gateway()
        text = str(payload.content) if hasattr(payload, "content") else str(payload)

        # Resolve external_chat_id from channel_accounts (required by sidecar /send)
        external_user_id = ""
        external_chat_id: str | None = None
        if user_id:
            external_user_id, external_chat_id = await _resolve_channel_account(user_id, channel)

        if not external_chat_id:
            logger.warning(
                "delivery_no_channel_account",
                target=target.value,
                user_id=str(user_id),
            )
            return

        msg = InternalMessage(
            direction="outbound",
            channel=channel,
            external_user_id=external_user_id,
            external_chat_id=external_chat_id,
            text=text,
        )
        await gateway.send_outbound(msg)
        logger.info("delivery_channel_sent", channel=channel, text_length=len(text))

    else:
        logger.error("delivery_target_unknown", target=str(target))


async def delivery_router_node(state: BlitzState) -> dict:
    """
    LangGraph node: route agent output to configured delivery targets.
    Reads delivery_targets from state (defaults to [WEB_CHAT]).
    Returns empty dict -- does not modify state (pure side-effect node).
    """
    targets_raw = state.get("delivery_targets", [DeliveryTarget.WEB_CHAT.value])
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None
    state_user_id: UUID | None = state.get("user_id")

    for target_str in targets_raw:
        try:
            target = DeliveryTarget(target_str)
        except ValueError:
            logger.error("delivery_target_invalid", target=target_str)
            continue
        await deliver(target, last_message, user_id=state_user_id)

    return {}
