"""
SSO state transition notification callback — Plan 26-01.

Creates AdminNotification in DB and dispatches Telegram alerts to admin users
when the SSO circuit breaker transitions state.
"""
import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import structlog
from sqlalchemy import select

from core.db import async_session
from core.models.admin_notification import AdminNotification

logger = structlog.get_logger(__name__)


async def on_sso_state_transition(
    old_state: str, new_state: str, reason: str
) -> None:
    """
    Circuit breaker state transition callback.

    1. Creates an AdminNotification in DB.
    2. Sends Telegram message to all it-admin users with linked Telegram accounts.
    """
    # Determine severity and message
    if new_state == "OPEN":
        severity = "critical"
        title = "SSO Circuit Breaker Opened"
        message = f"SSO is unavailable. Keycloak failures exceeded threshold. Reason: {reason}"
        emoji = "🔴"
    elif new_state == "CLOSED" and old_state in ("OPEN", "HALF_OPEN"):
        severity = "info"
        title = "SSO Recovered"
        message = f"SSO has recovered and is operational again. Reason: {reason}"
        emoji = "🟢"
    elif new_state == "HALF_OPEN":
        severity = "warning"
        title = "SSO Recovery Probe"
        message = f"Circuit breaker entering recovery probe mode. Reason: {reason}"
        emoji = "🟡"
    else:
        # Unknown transition — still log but don't alert
        logger.info(
            "sso_state_transition_unknown",
            old_state=old_state,
            new_state=new_state,
            reason=reason,
        )
        return

    # 1. Create DB notification
    try:
        async with async_session() as session:
            async with session.begin():
                notification = AdminNotification(
                    id=uuid4(),
                    category="sso_health",
                    severity=severity,
                    title=title,
                    message=message,
                    metadata_json=json.dumps({
                        "old_state": old_state,
                        "new_state": new_state,
                        "reason": reason,
                    }),
                )
                session.add(notification)
        logger.info(
            "sso_notification_created",
            severity=severity,
            title=title,
        )
    except Exception as exc:
        logger.warning("sso_notification_db_error", error=str(exc))

    # 2. Telegram alert to admin users
    await _send_telegram_alerts(emoji, title, message)


async def _send_telegram_alerts(emoji: str, title: str, message: str) -> None:
    """
    Send Telegram alerts to all it-admin users who have linked Telegram accounts.

    Uses the Telegram gateway sidecar's /send endpoint (same pattern as channel gateway).
    """
    try:
        from core.config import settings
        from core.models.channel import ChannelAccount
        from core.models.role_permission import RolePermission
        from core.models.local_auth import LocalUser, LocalUserRole

        gateway_url = settings.telegram_gateway_url
        if not gateway_url:
            logger.debug("sso_telegram_alert_skip", reason="No telegram_gateway_url configured")
            return

        # Find admin user_ids
        async with async_session() as session:
            # Get user_ids with it-admin role (local users)
            admin_result = await session.execute(
                select(LocalUserRole.user_id)
                .join(LocalUser, LocalUser.id == LocalUserRole.user_id)
                .where(LocalUserRole.role == "it-admin")
            )
            admin_user_ids = [row[0] for row in admin_result.all()]

            if not admin_user_ids:
                logger.debug("sso_telegram_alert_skip", reason="No admin users found")
                return

            # Find telegram accounts for these admin users
            telegram_result = await session.execute(
                select(ChannelAccount).where(
                    ChannelAccount.channel == "telegram",
                    ChannelAccount.is_paired == True,  # noqa: E712
                    ChannelAccount.user_id.in_(admin_user_ids),
                )
            )
            telegram_accounts = telegram_result.scalars().all()

        if not telegram_accounts:
            logger.debug("sso_telegram_alert_skip", reason="No admin Telegram accounts found")
            return

        # Send via sidecar
        text = f"{emoji} *{title}*\n\n{message}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            for account in telegram_accounts:
                try:
                    await client.post(
                        f"{gateway_url}/send",
                        json={
                            "channel": "telegram",
                            "external_user_id": account.external_user_id,
                            "text": text,
                            "user_id": str(account.user_id) if account.user_id else "",
                            "conversation_id": "",
                        },
                    )
                    logger.info(
                        "sso_telegram_alert_sent",
                        external_user_id=account.external_user_id,
                    )
                except Exception as exc:
                    logger.warning(
                        "sso_telegram_alert_failed",
                        external_user_id=account.external_user_id,
                        error=str(exc),
                    )

    except Exception as exc:
        logger.warning("sso_telegram_alerts_error", error=str(exc))
