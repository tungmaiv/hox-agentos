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

import structlog

from agents.state.types import BlitzState

logger = structlog.get_logger(__name__)


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


async def deliver(target: DeliveryTarget, payload: Any) -> None:
    """
    Route payload to the specified delivery target.

    WEB_CHAT: handled by CopilotKit/AG-UI automatically -- no action needed.
    TELEGRAM, WHATSAPP, TEAMS: real outbound via ChannelGateway.send_outbound().
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

    elif target == DeliveryTarget.TELEGRAM:
        from channels.models import InternalMessage

        gateway = _get_gateway()
        text = str(payload.content) if hasattr(payload, "content") else str(payload)
        msg = InternalMessage(
            direction="outbound",
            channel="telegram",
            external_user_id=getattr(payload, "external_user_id", ""),
            text=text,
        )
        await gateway.send_outbound(msg)
        logger.info("delivery_telegram_sent", text_length=len(text))

    elif target == DeliveryTarget.WHATSAPP:
        from channels.models import InternalMessage

        gateway = _get_gateway()
        text = str(payload.content) if hasattr(payload, "content") else str(payload)
        msg = InternalMessage(
            direction="outbound",
            channel="whatsapp",
            external_user_id=getattr(payload, "external_user_id", ""),
            text=text,
        )
        await gateway.send_outbound(msg)
        logger.info("delivery_whatsapp_sent", text_length=len(text))

    elif target == DeliveryTarget.TEAMS:
        from channels.models import InternalMessage

        gateway = _get_gateway()
        text = str(payload.content) if hasattr(payload, "content") else str(payload)
        msg = InternalMessage(
            direction="outbound",
            channel="ms_teams",
            external_user_id=getattr(payload, "external_user_id", ""),
            text=text,
        )
        await gateway.send_outbound(msg)
        logger.info("delivery_teams_sent", text_length=len(text))

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

    for target_str in targets_raw:
        try:
            target = DeliveryTarget(target_str)
        except ValueError:
            logger.error("delivery_target_invalid", target=target_str)
            continue
        await deliver(target, last_message)

    return {}
