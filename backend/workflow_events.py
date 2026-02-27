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

Race-condition fix (fast workflows):
  subscribe_events() accepts an optional get_run_status callback.
  After subscribing to the Redis channel (to avoid missing future events),
  it calls get_run_status() and, if the run is already terminal, immediately
  yields the synthetic terminal event without entering the pub/sub polling loop.
  This handles workflows that complete (0.06 s) before the SSE subscriber connects.
"""
import json
from collections.abc import Awaitable, Callable
from typing import Any, AsyncGenerator

import redis
import redis.asyncio as aioredis
import structlog

from core.config import get_settings

logger = structlog.get_logger(__name__)

_TERMINAL_EVENTS = {"workflow_completed", "workflow_failed", "workflow_rejected"}


def _channel_name(run_id: str) -> str:
    return f"workflow:events:{run_id}"


def _status_to_terminal_event(
    status: str, result_json: dict[str, Any] | None
) -> dict[str, Any] | None:
    """
    Convert a terminal DB run status to the corresponding SSE event dict.
    Returns None if the status is not terminal (pending, running).
    """
    rj = result_json or {}
    if status == "completed":
        return {"event": "workflow_completed", "output": rj.get("output")}
    if status == "failed":
        return {"event": "workflow_failed", "error": rj.get("error", "Workflow failed")}
    if status == "paused_hitl":
        return {
            "event": "hitl_paused",
            "message": rj.get("hitl_message", "Approval required"),
            "interrupt_data": rj.get("interrupt_data", {}),
        }
    return None


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
    *,
    get_run_status: Callable[[], Awaitable[tuple[str, dict[str, Any] | None]]] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Async generator that yields workflow events from Redis pub/sub.
    Stops when a terminal event is received or the timeout elapses.

    get_run_status — optional async callable that returns (status, result_json).
      When provided, it is called AFTER subscribing to the Redis channel (so no
      future events can be missed) to detect fast workflows that already finished
      before the SSE subscriber connected.

    Usage (FastAPI SSE endpoint):
        async for event in subscribe_events(run_id, get_run_status=check_db):
            yield f"data: {json.dumps(event)}\\n\\n"
    """
    settings = get_settings()
    r = aioredis.Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    # Subscribe FIRST so we cannot miss events published after this point.
    await pubsub.subscribe(_channel_name(run_id))

    try:
        # Fast-path: check if the run already reached a terminal state before
        # the SSE subscriber connected.  We check AFTER subscribing to guarantee
        # that any event published between subscribe() and this check will still
        # be waiting in the pub/sub buffer — so we cannot double-emit.
        if get_run_status is not None:
            status, result_json = await get_run_status()
            terminal_event = _status_to_terminal_event(status, result_json)
            if terminal_event is not None:
                logger.info(
                    "workflow_sse_fast_path",
                    run_id=run_id,
                    status=status,
                )
                yield terminal_event
                return  # unsubscribe happens in finally

        import asyncio
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
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
