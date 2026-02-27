"""
Formal ChannelAdapter protocol -- the pluggable interface for channel integrations.

Any class that implements `async def send(msg: InternalMessage) -> None` satisfies
this protocol. In practice, each channel runs as a Docker sidecar with a /send HTTP
endpoint, and ChannelGateway.send_outbound() handles the HTTP call. This Protocol
exists so that:

1. New channel implementers have a clear contract to follow
2. Type checkers (mypy, pyright) can verify protocol compliance
3. The requirement CHAN-05 is formally satisfied

The Protocol is @runtime_checkable so isinstance() can verify compliance at runtime.
"""
from typing import Protocol, runtime_checkable

from channels.models import InternalMessage


@runtime_checkable
class ChannelAdapter(Protocol):
    """
    Interface contract for channel adapters.

    Each channel (Telegram, WhatsApp, MS Teams) implements this protocol
    either as a Python class or as an HTTP sidecar service. The single
    required method is `send`, which delivers an outbound InternalMessage
    to the external platform.
    """

    async def send(self, msg: InternalMessage) -> None:
        """
        Deliver an outbound message to the external channel platform.

        Args:
            msg: The InternalMessage with direction="outbound", channel set
                 to the target platform, text and/or actions populated.

        Raises:
            httpx.HTTPStatusError: If the sidecar returns a non-2xx status.
            asyncio.TimeoutError: If the sidecar does not respond in time.
        """
        ...
