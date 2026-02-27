"""
Tests for the Redis pub/sub workflow event bus (workflow_events.py).

Verifies:
- publish_event() publishes JSON-encoded event to the correct Redis channel
- _channel_name() returns deterministic channel string including run_id
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_publish_event_publishes_to_redis():
    """publish_event serializes the event to JSON and publishes to the run's channel."""
    with patch("workflow_events.redis.Redis.from_url") as mock_redis_cls:
        mock_r = MagicMock()
        mock_redis_cls.return_value = mock_r

        from workflow_events import publish_event
        publish_event("run-123", {"event": "node_started", "node_id": "n1"})

        mock_r.publish.assert_called_once()
        channel, payload = mock_r.publish.call_args[0]
        assert channel == "workflow:events:run-123"
        assert json.loads(payload)["event"] == "node_started"


def test_get_event_channel_name():
    """Channel name must be deterministic and include run_id."""
    from workflow_events import _channel_name
    assert _channel_name("abc-123") == "workflow:events:abc-123"
