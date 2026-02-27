"""
Platform-agnostic message models for the multi-channel integration layer.

InternalMessage is the canonical format shared between:
  - Channel sidecars (Telegram, WhatsApp, Teams)
  - Backend ChannelGateway
  - Agent invocation and response delivery

All sidecars translate platform-specific events INTO InternalMessage (inbound)
and FROM InternalMessage (outbound). The backend never sees platform-specific payloads.
"""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class MessageAction(BaseModel):
    """An inline button attached to an outbound message."""

    label: str
    action_id: str
    style: Literal["primary", "secondary", "danger"] = "primary"


class Attachment(BaseModel):
    """A file or media item attached to a message."""

    type: Literal["image", "file", "audio", "video"]
    url: str | None = None
    file_path: str | None = None
    mime_type: str | None = None


class InternalMessage(BaseModel):
    """
    Canonical message format for all channels.

    Inbound: sidecar -> backend (user_id and conversation_id filled by gateway)
    Outbound: backend -> sidecar (all fields filled)
    """

    direction: Literal["inbound", "outbound"]
    channel: Literal["telegram", "whatsapp", "ms_teams", "web"]
    external_user_id: str
    external_chat_id: str | None = None
    user_id: UUID | None = None
    conversation_id: UUID | None = None
    text: str | None = None
    attachments: list[Attachment] = []
    actions: list[MessageAction] = []
    is_group: bool = False
    metadata: dict = {}
