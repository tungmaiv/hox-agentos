"""Tests for InternalMessage and related Pydantic models."""
import uuid

import pytest

from channels.models import Attachment, InternalMessage, MessageAction


def test_inbound_message_minimal():
    msg = InternalMessage(
        direction="inbound",
        channel="telegram",
        external_user_id="12345",
        text="Hello",
    )
    assert msg.direction == "inbound"
    assert msg.channel == "telegram"
    assert msg.user_id is None
    assert msg.actions == []
    assert msg.attachments == []
    assert msg.is_group is False


def test_outbound_message_with_actions():
    msg = InternalMessage(
        direction="outbound",
        channel="whatsapp",
        external_user_id="+84912345678",
        external_chat_id="+84912345678",
        user_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        text="Do you approve this task?",
        actions=[
            MessageAction(label="Approve", action_id="approve_123", style="primary"),
            MessageAction(label="Reject", action_id="reject_123", style="danger"),
        ],
    )
    assert len(msg.actions) == 2
    assert msg.actions[0].label == "Approve"
    assert msg.actions[1].style == "danger"


def test_message_with_attachment():
    msg = InternalMessage(
        direction="inbound",
        channel="telegram",
        external_user_id="99999",
        attachments=[
            Attachment(type="image", url="https://example.com/photo.jpg", mime_type="image/jpeg"),
        ],
    )
    assert len(msg.attachments) == 1
    assert msg.attachments[0].type == "image"


def test_json_roundtrip():
    original = InternalMessage(
        direction="outbound",
        channel="ms_teams",
        external_user_id="teams-user-id",
        text="Summary report",
        actions=[MessageAction(label="View", action_id="view_1")],
    )
    json_str = original.model_dump_json()
    restored = InternalMessage.model_validate_json(json_str)
    assert restored.channel == "ms_teams"
    assert restored.actions[0].label == "View"


def test_invalid_channel_rejected():
    with pytest.raises(Exception):
        InternalMessage(
            direction="inbound",
            channel="discord",  # not in Literal
            external_user_id="123",
        )


def test_invalid_direction_rejected():
    with pytest.raises(Exception):
        InternalMessage(
            direction="sideways",  # not in Literal
            channel="telegram",
            external_user_id="123",
        )
