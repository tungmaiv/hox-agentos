"""
DeliveryRouterNode — deterministic output routing at end of master agent graph.
NOT a sub-agent (no LLM calls). Routes formatted response to delivery target(s).

Per CONTEXT.md decision:
- WEB_CHAT: active in Phase 3 (CopilotKit handles this automatically via AG-UI)
- EMAIL_NOTIFY, TELEGRAM, TEAMS: stubs — log warning + no-op in Phase 3
  Phase 5 ChannelAdapter implementations will plug into deliver() without changing this file.

This is distinct from Phase 5 ChannelAdapter (inbound):
- DeliveryRouterNode = outbound (Phase 3)
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
    TEAMS = "TEAMS"


def deliver(target: DeliveryTarget, payload: Any) -> None:
    """
    Route payload to the specified delivery target.
    Phase 3: only WEB_CHAT is active. Others log warning and no-op.
    Phase 5: replace no-ops with real ChannelAdapter calls.
    """
    if target == DeliveryTarget.WEB_CHAT:
        # WEB_CHAT delivery is handled by CopilotKit/AG-UI automatically.
        # No additional action needed here.
        logger.debug("delivery_web_chat", payload_type=type(payload).__name__)
    elif target == DeliveryTarget.EMAIL_NOTIFY:
        logger.warning(
            "delivery_target_stub_not_implemented",
            target=target.value,
            note="Email notification delivery not implemented until Phase 5",
        )
    elif target == DeliveryTarget.TELEGRAM:
        logger.warning(
            "delivery_target_stub_not_implemented",
            target=target.value,
            note="Telegram delivery not implemented until Phase 5",
        )
    elif target == DeliveryTarget.TEAMS:
        logger.warning(
            "delivery_target_stub_not_implemented",
            target=target.value,
            note="Teams delivery not implemented until Phase 5",
        )
    else:
        logger.error("delivery_target_unknown", target=str(target))


async def delivery_router_node(state: BlitzState) -> dict:
    """
    LangGraph node: route agent output to configured delivery targets.
    Reads delivery_targets from state (defaults to [WEB_CHAT]).
    Returns empty dict — does not modify state (pure side-effect node).
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
        deliver(target, last_message)

    return {}
