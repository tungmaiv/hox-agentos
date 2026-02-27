"""
Workflow event bus using Redis pub/sub.

publish_event()    — sync, called from Celery workers (asyncio.run context).
subscribe_events() — async generator, called from FastAPI SSE endpoints.

Channel naming: "workflow:events:{run_id}"

Event envelope (JSON-serialized):
  {"event": "node_started",    "node_id": "<id>"}
  {"event": "node_completed",  "node_id": "<id>", "output": {...}}
  {"event": "hitl_paused",     "node_id": "<id>", "message": "..."}
  {"event": "workflow_completed", "output": {...}}
  {"event": "workflow_failed",    "error":  "..."}
  {"event": "workflow_rejected"}

Terminal events (workflow_completed, workflow_failed, workflow_rejected)
cause subscribe_events() to stop yielding.
"""
import json
from typing import Any, AsyncGenerator

import redis
import redis.asyncio as aioredis
import structlog

from core.config import get_settings

logger = structlog.get_logger(__name__)

_TERMINAL_EVENTS = {"workflow_completed", "workflow_failed", "workflow_rejected"}


def _channel_name(run_id: str) -> str:
    return f"workflow:events:{run_id}"


def publish_event(run_id: str, event: dict[str, Any]) -> None:
    """
    Publish a workflow event to Redis pub/sub.
    Sync — safe to call from Celery workers (both sync and asyncio.run contexts).
    """
    settings = get_settings()
    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        r.publish(_channel_name(run_id), json.dumps(event))
    finally:
        r.close()


async def subscribe_events(
    run_id: str,
    timeout_seconds: float = 300.0,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Async generator that yields workflow events from Redis pub/sub.
    Stops when a terminal event is received or the timeout elapses.

    Usage (FastAPI SSE endpoint):
        async for event in subscribe_events(run_id):
            yield f"data: {json.dumps(event)}\\n\\n"
    """
    settings = get_settings()
    r = aioredis.Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(_channel_name(run_id))

    try:
        import asyncio
        deadline = asyncio.get_event_loop().time() + timeout_seconds
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                logger.warning("workflow_sse_timeout", run_id=run_id)
                break

            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=min(30.0, remaining),
            )
            if message is None:
                # Keepalive — SSE client stays connected
                yield {"event": "keepalive"}
                continue

            try:
                event = json.loads(message["data"])
            except (json.JSONDecodeError, KeyError):
                continue

            yield event

            if event.get("event") in _TERMINAL_EVENTS:
                break
    finally:
        await pubsub.unsubscribe(_channel_name(run_id))
        await r.aclose()
