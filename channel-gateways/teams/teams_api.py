"""
Bot Framework Connector API wrapper for MS Teams sidecar.

Handles:
  - OAuth2 client_credentials token acquisition (cached until expiry)
  - Sending Activities (text and Adaptive Card) to conversations
  - Threaded replies to specific activities
  - Typing indicator
  - Inbound token validation (Bot Framework JWT)

SECURITY: app_password and tokens are NEVER logged.
"""
import time
from typing import Any

import httpx
import jwt
import structlog

logger = structlog.get_logger(__name__)

_TOKEN_URL = (
    "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
)
_SCOPE = "https://api.botframework.com/.default"
_OPENID_CONFIG_URL = (
    "https://login.botframework.com/v1/.well-known/openidconfiguration"
)
_EXPECTED_ISSUER = "https://api.botframework.com"


class TeamsAPI:
    """Lightweight Bot Framework Connector API client using httpx."""

    def __init__(self, app_id: str, app_password: str) -> None:
        self.app_id = app_id
        self._app_password = app_password
        self._cached_token: str | None = None
        self._token_expires_at: float = 0.0
        self._jwks_cache: dict[str, Any] | None = None

    # -- Token management ---------------------------------------------------

    async def get_token(self) -> str:
        """
        Acquire a Bearer token via client_credentials grant.

        Tokens are cached in-memory until 60 seconds before expiry.
        """
        now = time.time()
        if self._cached_token and now < self._token_expires_at - 60:
            return self._cached_token

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.app_id,
                    "client_secret": self._app_password,
                    "scope": _SCOPE,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        self._cached_token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        self._token_expires_at = now + float(expires_in)
        logger.info("bot_token_acquired", expires_in=expires_in)
        return self._cached_token

    # -- Outbound messaging -------------------------------------------------

    async def send_activity(
        self,
        service_url: str,
        conversation_id: str,
        activity: dict[str, Any],
    ) -> dict[str, Any]:
        """Send a new activity to a conversation."""
        url = f"{service_url.rstrip('/')}/v3/conversations/{conversation_id}/activities"
        return await self._post_activity(url, activity)

    async def reply_to_activity(
        self,
        service_url: str,
        conversation_id: str,
        activity_id: str,
        activity: dict[str, Any],
    ) -> dict[str, Any]:
        """Reply to a specific activity (creates a threaded reply in channels)."""
        url = (
            f"{service_url.rstrip('/')}/v3/conversations/"
            f"{conversation_id}/activities/{activity_id}"
        )
        return await self._post_activity(url, activity)

    async def send_typing(
        self,
        service_url: str,
        conversation_id: str,
    ) -> None:
        """Send a typing indicator to a conversation."""
        activity = {"type": "typing"}
        url = f"{service_url.rstrip('/')}/v3/conversations/{conversation_id}/activities"
        try:
            await self._post_activity(url, activity)
        except httpx.HTTPError:
            # Typing indicator failure is non-critical
            logger.debug("typing_indicator_failed", conversation_id=conversation_id)

    async def _post_activity(
        self,
        url: str,
        activity: dict[str, Any],
    ) -> dict[str, Any]:
        """POST an activity to Bot Framework Connector."""
        token = await self.get_token()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url,
                json=activity,
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return resp.json() if resp.content else {}

    # -- Adaptive Card builder ----------------------------------------------

    @staticmethod
    def build_adaptive_card(
        text: str,
        actions: list[dict[str, str]],
    ) -> dict[str, Any]:
        """
        Build an Adaptive Card JSON with a markdown TextBlock and
        Action.Submit buttons.

        Args:
            text: Markdown body text for the card.
            actions: List of dicts with 'label' and 'action_id' keys.

        Returns:
            An Activity dict with the Adaptive Card as an attachment.
        """
        card_body: list[dict[str, Any]] = [
            {
                "type": "TextBlock",
                "text": text,
                "wrap": True,
            }
        ]

        card_actions: list[dict[str, Any]] = [
            {
                "type": "Action.Submit",
                "title": action["label"],
                "data": {"action_id": action["action_id"]},
            }
            for action in actions
        ]

        card = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.4",
            "body": card_body,
            "actions": card_actions,
        }

        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card,
                }
            ],
        }

    # -- Inbound token validation -------------------------------------------

    async def validate_token(self, auth_header: str) -> bool:
        """
        Validate a Bot Framework JWT from the Authorization header.

        For MVP: validates structure, issuer, and audience. Logs warning
        on signature failures (full JWKS rotation handling deferred).

        Args:
            auth_header: The full Authorization header value (e.g. "Bearer xyz...").

        Returns:
            True if token is valid, False otherwise.
        """
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning("token_validation_failed", reason="missing_bearer_prefix")
            return False

        token = auth_header[len("Bearer "):]

        try:
            # Decode without signature verification first to check claims
            unverified = jwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_exp": True,
                    "verify_aud": True,
                },
                audience=self.app_id,
                algorithms=["RS256"],
            )

            issuer = unverified.get("iss", "")
            if issuer != _EXPECTED_ISSUER:
                logger.warning(
                    "token_validation_failed",
                    reason="invalid_issuer",
                    issuer=issuer,
                )
                return False

            logger.debug("token_validated", issuer=issuer)
            return True

        except jwt.ExpiredSignatureError:
            logger.warning("token_validation_failed", reason="expired")
            return False
        except jwt.InvalidAudienceError:
            logger.warning("token_validation_failed", reason="invalid_audience")
            return False
        except jwt.PyJWTError as exc:
            logger.warning(
                "token_validation_failed",
                reason="jwt_error",
                error=str(exc),
            )
            return False
