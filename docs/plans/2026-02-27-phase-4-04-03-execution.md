# Phase 4 — Plan 04-03: Workflow Execution Engine

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Execute compiled workflows end-to-end — Celery task runs the graph, SSE streams node-level events to the canvas, the real MCP tool handler replaces the stub, and a Celery beat scheduler fires cron triggers every minute.

**Architecture:** Celery worker calls `execute_workflow(run_id)` → compiles graph → runs `astream_events()` → publishes events to Redis pub/sub (`workflow:events:{run_id}`). FastAPI SSE endpoint subscribes to that Redis channel and streams to the browser. `GraphInterrupt` from HITL nodes is caught and sets status to `paused_hitl` (resume wired in 04-04). The `tool_node` handler is updated to call `call_mcp_tool()` with a real DB session and a constructed `UserContext`.

**Tech Stack:** Celery 5+, `redis.asyncio` (SSE subscribe), `redis` sync (worker publish), LangGraph `astream_events`, `langgraph.errors.GraphInterrupt`.

---

## Task 1: Wire `_handle_tool_node` with Real MCP Calls

**Files:**
- Modify: `backend/agents/node_handlers.py`
- Test: `backend/tests/agents/test_tool_node_handler.py`

The tool node handler in 04-02 was a stub. Replace it with a real call to `call_mcp_tool()` from `mcp/registry.py`.

**Important:** `call_mcp_tool` requires a `UserContext` TypedDict with `user_id: UUID` (not str). The handler must construct one from `state["user_context"]`. It also requires an `AsyncSession` — create one using `async_session()` inside the handler.

**Step 1: Write failing tests**

```python
# backend/tests/agents/test_tool_node_handler.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from agents.workflow_state import WorkflowState


def _make_state(user_id: str | None = None) -> WorkflowState:
    return {
        "run_id": uuid4(),
        "user_context": {
            "user_id": user_id or str(uuid4()),
            "email": "test@blitz.local",
            "username": "testuser",
            "roles": ["employee"],
            "groups": [],
        },
        "node_outputs": {},
        "current_output": None,
        "hitl_result": None,
    }


@pytest.mark.asyncio
async def test_tool_node_returns_error_for_unknown_tool():
    """Unknown tool name returns error dict, does not raise."""
    from agents.node_handlers import get_handler
    handler = get_handler("tool_node")
    state = _make_state()
    result = await handler({"tool_name": "nonexistent.tool", "params": {}}, state)
    assert result["success"] is False
    assert "not registered" in result["error"]


@pytest.mark.asyncio
async def test_tool_node_calls_mcp_for_known_tool():
    """Known tool delegates to call_mcp_tool."""
    from agents.node_handlers import get_handler

    mock_result = {"projects": ["Alpha", "Beta"], "count": 2}

    with patch("agents.node_handlers.call_mcp_tool", new_callable=AsyncMock) as mock_call, \
         patch("agents.node_handlers.async_session") as mock_session_factory:

        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_call.return_value = mock_result

        handler = get_handler("tool_node")
        state = _make_state()
        result = await handler(
            {"tool_name": "crm.list_projects", "params": {"limit": 10}},
            state,
        )

    assert result == mock_result
    mock_call.assert_called_once()
    call_kwargs = mock_call.call_args
    assert call_kwargs[1]["tool_name"] == "crm.list_projects"
    assert call_kwargs[1]["arguments"] == {"limit": 10}


@pytest.mark.asyncio
async def test_tool_node_returns_error_on_acl_denial():
    """ACL denial (HTTPException 403) is caught and returned as error dict."""
    from agents.node_handlers import get_handler
    from fastapi import HTTPException

    with patch("agents.node_handlers.call_mcp_tool", new_callable=AsyncMock) as mock_call, \
         patch("agents.node_handlers.async_session") as mock_session_factory:

        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_call.side_effect = HTTPException(status_code=403, detail="Tool call denied by ACL")

        handler = get_handler("tool_node")
        state = _make_state()
        result = await handler({"tool_name": "crm.list_projects", "params": {}}, state)

    assert result["success"] is False
    assert "403" in result["error"] or "denied" in result["error"].lower()
```

**Step 2: Run to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/agents/test_tool_node_handler.py -v
```
Expected: test_tool_node_calls_mcp_for_known_tool and test_tool_node_returns_error_on_acl_denial fail (stub doesn't call call_mcp_tool).

**Step 3: Update `_handle_tool_node` in `backend/agents/node_handlers.py`**

Replace the existing `_handle_tool_node` function with:

```python
async def _handle_tool_node(config: dict[str, Any], state: WorkflowState) -> Any:
    """
    Call a registered MCP tool through all 3 security gates.

    Config fields:
      tool_name: tool identifier registered in gateway/tool_registry.py
      params:    dict of tool parameters passed as MCP arguments

    Security: delegates to mcp.registry.call_mcp_tool which enforces
    Gate 2 (RBAC) and Gate 3 (ACL). Gate 1 is satisfied because user_context
    was already validated by the workflow's owner JWT before execution.

    Returns the MCP tool result dict, or an error dict if the call fails.
    """
    from fastapi import HTTPException
    from mcp.registry import call_mcp_tool
    from core.db import async_session
    from core.models.user import UserContext

    tool_name = config.get("tool_name", "")
    params = config.get("params", {})

    # Unknown tool: fail fast before opening a DB session
    from gateway.tool_registry import get_tool
    if get_tool(tool_name) is None:
        logger.warning("tool_node_unknown_tool", tool_name=tool_name)
        return {"error": f"Tool '{tool_name}' not registered", "success": False}

    # Build UserContext from workflow state — user_id must be UUID
    raw_ctx = state.get("user_context") or {}
    try:
        user_uuid = uuid.UUID(str(raw_ctx.get("user_id", "")))
    except ValueError:
        return {"error": "Invalid user_id in workflow state", "success": False}

    user_ctx: UserContext = {
        "user_id": user_uuid,
        "email": str(raw_ctx.get("email", "")),
        "username": str(raw_ctx.get("username", "")),
        "roles": list(raw_ctx.get("roles", [])),
        "groups": list(raw_ctx.get("groups", [])),
    }

    try:
        async with async_session() as session:
            result = await call_mcp_tool(
                tool_name=tool_name,
                arguments=params,
                user=user_ctx,
                db_session=session,
            )
        logger.info("tool_node_success", tool=tool_name, user_id=str(user_uuid))
        return result
    except HTTPException as exc:
        logger.warning(
            "tool_node_denied",
            tool=tool_name,
            status_code=exc.status_code,
            detail=exc.detail,
        )
        return {"error": f"{exc.status_code}: {exc.detail}", "success": False}
    except Exception as exc:
        logger.error("tool_node_error", tool=tool_name, error=str(exc))
        return {"error": str(exc), "success": False}
```

Also add `import uuid` at the top of `node_handlers.py` if not already present.

**Step 4: Run tests**

```bash
cd backend && .venv/bin/pytest tests/agents/test_tool_node_handler.py -v
```
Expected: 3 tests PASS

**Step 5: Commit**

```bash
git add backend/agents/node_handlers.py backend/tests/agents/test_tool_node_handler.py
git commit -m "feat(04-03): wire tool_node handler to real MCP call_mcp_tool"
```

---

## Task 2: Redis Event Bus for SSE

**Files:**
- Create: `backend/workflow_events.py`
- Test: `backend/tests/test_workflow_events.py`

Celery workers and FastAPI run in separate processes. In-memory queues won't work. Use Redis pub/sub: worker publishes, FastAPI SSE endpoint subscribes.

**Step 1: Write failing tests**

```python
# backend/tests/test_workflow_events.py
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
```

**Step 2: Run to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_workflow_events.py -v
```
Expected: `ImportError: No module named 'workflow_events'`

**Step 3: Create `backend/workflow_events.py`**

```python
"""
Workflow event bus using Redis pub/sub.

publish_event()  — sync, called from Celery workers (asyncio.run context).
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
            yield f"data: {json.dumps(event)}\n\n"
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
```

**Step 4: Run tests**

```bash
cd backend && .venv/bin/pytest tests/test_workflow_events.py -v
```
Expected: 2 tests PASS

**Step 5: Commit**

```bash
git add backend/workflow_events.py backend/tests/test_workflow_events.py
git commit -m "feat(04-03): add Redis pub/sub workflow event bus"
```

---

## Task 3: Celery Execution Task

**Files:**
- Create: `backend/scheduler/tasks/workflow_execution.py`
- Modify: `backend/scheduler/celery_app.py`
- Test: `backend/tests/scheduler/test_workflow_execution.py`

**Step 1: Write failing tests**

```python
# backend/tests/scheduler/test_workflow_execution.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import uuid4


@pytest.mark.asyncio
async def test_execute_workflow_not_found_exits_silently():
    """Missing WorkflowRun logs error and returns without raising."""
    with patch("scheduler.tasks.workflow_execution.async_session") as mock_sf, \
         patch("scheduler.tasks.workflow_execution.publish_event") as mock_pub:

        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        from scheduler.tasks.workflow_execution import execute_workflow
        await execute_workflow(str(uuid4()))

        mock_pub.assert_not_called()


@pytest.mark.asyncio
async def test_execute_workflow_compile_failure_sets_failed_status():
    """Compiler ValueError sets run.status = 'failed'."""
    run_id = str(uuid4())

    mock_run = MagicMock()
    mock_run.id = uuid4()
    mock_run.workflow_id = uuid4()
    mock_run.owner_user_id = uuid4()
    mock_run.status = "pending"

    mock_workflow = MagicMock()
    mock_workflow.definition_json = {"schema_version": "BAD", "nodes": [], "edges": []}

    with patch("scheduler.tasks.workflow_execution.async_session") as mock_sf, \
         patch("scheduler.tasks.workflow_execution.publish_event") as mock_pub:

        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_run)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_workflow)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_run)),
        ])
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        from scheduler.tasks.workflow_execution import execute_workflow
        await execute_workflow(run_id)

        # Status must be set to failed
        assert mock_run.status == "failed"
        # workflow_failed event must be published
        published_events = [c[0][1]["event"] for c in mock_pub.call_args_list]
        assert "workflow_failed" in published_events
```

**Step 2: Run to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/scheduler/test_workflow_execution.py -v
```
Expected: `ImportError: No module named 'scheduler.tasks.workflow_execution'`

**Step 3: Create `backend/scheduler/tasks/workflow_execution.py`**

```python
"""
Workflow execution Celery task.

execute_workflow_task(run_id_str):  Celery entry point (sync wrapper).
execute_workflow(run_id_str):       Main async execution logic.

Execution flow:
  1. Load WorkflowRun + Workflow from DB
  2. Build UserContext from run.owner_user_id
  3. Set run.status = "running", commit
  4. compile_workflow_to_stategraph(definition_json, user_context)
  5. Compile with MemorySaver (04-04 replaces with AsyncPostgresSaver for HITL)
  6. astream_events() — publish SSE events to Redis for each node
  7. On completion: set run.status = "completed", store result_json
  8. On GraphInterrupt (HITL): set run.status = "paused_hitl", publish hitl_paused event
  9. On error: set run.status = "failed", publish workflow_failed event

Security: Celery workers run as the job owner (WorkflowRun.owner_user_id).
Full 3-gate ACL is enforced inside node handlers (see node_handlers.py).
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select

from agents.graphs import compile_workflow_to_stategraph
from core.db import async_session
from core.models.workflow import Workflow, WorkflowRun
from scheduler.celery_app import celery_app
from workflow_events import publish_event

logger = structlog.get_logger(__name__)


@celery_app.task(
    name="scheduler.tasks.workflow_execution.execute_workflow_task",
    queue="default",
    bind=True,
    max_retries=0,  # Workflow failures are not retried automatically
)
def execute_workflow_task(self, run_id_str: str, hitl_result: str | None = None) -> None:  # type: ignore[override]
    """Celery entry point — bridges sync Celery to async execution."""
    asyncio.run(execute_workflow(run_id_str, hitl_result=hitl_result))


async def execute_workflow(run_id_str: str, hitl_result: str | None = None) -> None:
    """Main async workflow execution logic."""
    run_id = uuid.UUID(run_id_str)

    # ── 1. Load WorkflowRun ───────────────────────────────────────────────────
    async with async_session() as session:
        result = await session.execute(
            select(WorkflowRun).where(WorkflowRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if run is None:
            logger.error("workflow_run_not_found", run_id=run_id_str)
            return

        result = await session.execute(
            select(Workflow).where(Workflow.id == run.workflow_id)
        )
        workflow = result.scalar_one_or_none()
        if workflow is None:
            run.status = "failed"
            run.result_json = {"error": "Workflow definition not found"}
            await session.commit()
            publish_event(run_id_str, {"event": "workflow_failed", "error": "Workflow not found"})
            return

        owner_user_id = run.owner_user_id
        definition_json = workflow.definition_json
        run.status = "running"
        await session.commit()

    # ── 2. Build user context (runs as job owner) ─────────────────────────────
    user_context: dict[str, Any] = {
        "user_id": str(owner_user_id),
        "email": "",       # Not available in worker — ACL only needs user_id + roles
        "username": "",
        "roles": ["employee"],
        "groups": [],
    }

    # ── 3. Compile ────────────────────────────────────────────────────────────
    try:
        builder = compile_workflow_to_stategraph(definition_json, user_context)
    except Exception as exc:
        logger.error("workflow_compile_failed", run_id=run_id_str, error=str(exc))
        async with async_session() as session:
            result = await session.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
            run = result.scalar_one_or_none()
            if run:
                run.status = "failed"
                run.result_json = {"error": f"Compile error: {exc}"}
                await session.commit()
        publish_event(run_id_str, {"event": "workflow_failed", "error": str(exc)})
        return

    # ── 4. Attach checkpointer and execute ────────────────────────────────────
    # TODO(04-04): Replace MemorySaver with AsyncPostgresSaver for HITL persistence
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()
    compiled = builder.compile(checkpointer=checkpointer)

    # Known node IDs from the definition (used to filter astream_events noise)
    known_node_ids: set[str] = {n["id"] for n in definition_json.get("nodes", [])}

    initial_state: dict[str, Any] = {
        "run_id": run_id,
        "user_context": user_context,
        "node_outputs": {},
        "current_output": None,
        "hitl_result": hitl_result,  # None for fresh run, "approved"/"rejected" on resume
    }
    config = {"configurable": {"thread_id": run_id_str}}

    final_output: Any = None

    try:
        async for event in compiled.astream_events(initial_state, config=config, version="v1"):
            event_type: str = event.get("event", "")
            node_name: str = event.get("name", "")

            # Only emit events for our workflow nodes (filter LangGraph internals)
            if node_name not in known_node_ids:
                continue

            if event_type == "on_chain_start":
                publish_event(run_id_str, {"event": "node_started", "node_id": node_name})

            elif event_type == "on_chain_end":
                output = event.get("data", {}).get("output", {})
                current = output.get("current_output") if isinstance(output, dict) else output
                final_output = current
                publish_event(run_id_str, {
                    "event": "node_completed",
                    "node_id": node_name,
                    "output": current,
                })

    except Exception as exc:
        # Check for GraphInterrupt (HITL pause)
        exc_type = type(exc).__name__
        if "Interrupt" in exc_type or "GraphInterrupt" in exc_type:
            # Extract interrupt data — LangGraph stores it in exc.args or exc.interrupts
            interrupt_data: dict[str, Any] = {}
            if hasattr(exc, "interrupts") and exc.interrupts:
                raw = exc.interrupts[0]
                interrupt_data = raw.value if hasattr(raw, "value") else {}
            elif exc.args:
                raw = exc.args[0]
                interrupt_data = raw[0].value if (isinstance(raw, (list, tuple)) and raw and hasattr(raw[0], "value")) else {}

            message = interrupt_data.get("message", "Approval required to continue.")

            # Find the HITL node_id — it's the last node that published node_started
            # We store the paused node_id in result_json for resume
            async with async_session() as session:
                result = await session.execute(
                    select(WorkflowRun).where(WorkflowRun.id == run_id)
                )
                run = result.scalar_one_or_none()
                if run:
                    run.status = "paused_hitl"
                    run.checkpoint_id = run_id_str  # thread_id for AsyncPostgresSaver resume
                    run.result_json = {"hitl_message": message, "interrupt_data": interrupt_data}
                    await session.commit()

            publish_event(run_id_str, {
                "event": "hitl_paused",
                "message": message,
                "interrupt_data": interrupt_data,
            })
            logger.info("workflow_paused_hitl", run_id=run_id_str, message=message)
            return

        # Genuine error
        logger.error("workflow_execution_error", run_id=run_id_str, error=str(exc), exc_type=exc_type)
        async with async_session() as session:
            result = await session.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
            run = result.scalar_one_or_none()
            if run:
                run.status = "failed"
                run.result_json = {"error": str(exc)}
                await session.commit()
        publish_event(run_id_str, {"event": "workflow_failed", "error": str(exc)})
        return

    # ── 5. Mark completed ─────────────────────────────────────────────────────
    async with async_session() as session:
        result = await session.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
        run = result.scalar_one_or_none()
        if run:
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            run.result_json = {"output": final_output}
            await session.commit()

    publish_event(run_id_str, {"event": "workflow_completed", "output": final_output})
    logger.info("workflow_completed", run_id=run_id_str)
```

**Step 4: Register the task module in `backend/scheduler/celery_app.py`**

Open `backend/scheduler/celery_app.py` and update the `include` list:

```python
# Change:
include=["scheduler.tasks.embedding"],

# To:
include=[
    "scheduler.tasks.embedding",
    "scheduler.tasks.workflow_execution",
    "scheduler.tasks.cron_trigger",   # added in Task 5
],
```

Also add the task routes:
```python
task_routes={
    "scheduler.tasks.embedding.embed_and_store": {"queue": "embedding"},
    "scheduler.tasks.embedding.summarize_episode": {"queue": "default"},
    "scheduler.tasks.workflow_execution.execute_workflow_task": {"queue": "default"},
    "scheduler.tasks.cron_trigger.fire_cron_triggers_task": {"queue": "default"},
},
```

**Step 5: Run tests**

```bash
cd backend && .venv/bin/pytest tests/scheduler/test_workflow_execution.py -v
```
Expected: 2 tests PASS

**Step 6: Commit**

```bash
git add backend/scheduler/tasks/workflow_execution.py backend/scheduler/celery_app.py backend/tests/scheduler/test_workflow_execution.py
git commit -m "feat(04-03): add workflow execution Celery task with SSE event publishing"
```

---

## Task 4: Add Run + SSE Endpoints to the Workflows Router

**Files:**
- Modify: `backend/api/routes/workflows.py`
- Test: `backend/tests/test_workflows_run_api.py`

**Step 1: Write failing tests**

```python
# backend/tests/test_workflows_run_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4

MOCK_USER = {
    "user_id": str(uuid4()),
    "email": "t@blitz.local",
    "username": "t",
    "roles": ["employee"],
    "groups": [],
}


@pytest.mark.asyncio
async def test_run_workflow_not_found():
    """Running a non-existent workflow returns 404."""
    from main import app
    with patch("security.deps.get_current_user", return_value=MOCK_USER):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/workflows/{uuid4()}/run",
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_approve_run_not_found():
    """Approving a non-existent run returns 404."""
    from main import app
    with patch("security.deps.get_current_user", return_value=MOCK_USER):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/workflows/runs/{uuid4()}/approve",
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reject_run_not_found():
    """Rejecting a non-existent run returns 404."""
    from main import app
    with patch("security.deps.get_current_user", return_value=MOCK_USER):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/workflows/runs/{uuid4()}/reject",
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_approve_run_wrong_status_returns_409():
    """Approving a run that is not paused_hitl returns 409."""
    from main import app

    mock_run = MagicMock()
    mock_run.id = uuid4()
    mock_run.workflow_id = uuid4()
    mock_run.owner_user_id = uuid4()
    mock_run.status = "running"   # not paused_hitl

    with patch("security.deps.get_current_user", return_value=MOCK_USER), \
         patch("api.routes.workflows._get_user_run", new_callable=AsyncMock, return_value=mock_run):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/workflows/runs/{mock_run.id}/approve",
                headers={"Authorization": "Bearer fake"},
            )
    assert response.status_code == 409
```

**Step 2: Run to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/test_workflows_run_api.py -v
```
Expected: test_approve_run_not_found and test_reject_run_not_found fail (routes not yet added).

**Step 3: Add run + SSE + approve/reject endpoints to `backend/api/routes/workflows.py`**

Add these imports at the top:
```python
import json
from fastapi.responses import StreamingResponse
from workflow_events import subscribe_events
from scheduler.tasks.workflow_execution import execute_workflow_task
```

Add these routes to the router (before the `/{workflow_id}` routes to avoid path conflicts):

```python
@router.post("/{workflow_id}/run", response_model=WorkflowRunResponse, status_code=status.HTTP_201_CREATED)
async def run_workflow(
    workflow_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkflowRunResponse:
    """Create a WorkflowRun and enqueue the execution Celery task."""
    workflow = await _get_user_workflow(workflow_id, uuid.UUID(user["user_id"]), session)
    run = WorkflowRun(
        workflow_id=workflow.id,
        owner_user_id=uuid.UUID(user["user_id"]),
        trigger_type="manual",
        status="pending",
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    execute_workflow_task.delay(str(run.id))
    logger.info("workflow_run_enqueued", run_id=str(run.id), workflow_id=str(workflow_id))
    return WorkflowRunResponse.model_validate(run)


@router.get("/runs/{run_id}/events")
async def stream_run_events(
    run_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
) -> StreamingResponse:
    """SSE stream — yields node status events until the workflow completes."""
    run_id_str = str(run_id)

    async def _event_generator():
        async for event in subscribe_events(run_id_str):
            if event.get("event") == "keepalive":
                yield ": keepalive\n\n"
            else:
                yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/runs/{run_id}/approve", response_model=WorkflowRunResponse)
async def approve_run(
    run_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkflowRunResponse:
    """Resume a paused_hitl workflow with approval."""
    run = await _get_user_run(run_id, uuid.UUID(user["user_id"]), session)
    if run.status != "paused_hitl":
        raise HTTPException(
            status_code=409,
            detail=f"Run status is '{run.status}', expected 'paused_hitl'",
        )
    run.status = "running"
    await session.commit()
    execute_workflow_task.delay(str(run.id), hitl_result="approved")
    logger.info("workflow_run_approved", run_id=str(run_id), user_id=user["user_id"])
    return WorkflowRunResponse.model_validate(run)


@router.post("/runs/{run_id}/reject", response_model=WorkflowRunResponse)
async def reject_run(
    run_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkflowRunResponse:
    """Reject a paused_hitl workflow — marks it failed."""
    from workflow_events import publish_event as _pub
    run = await _get_user_run(run_id, uuid.UUID(user["user_id"]), session)
    if run.status != "paused_hitl":
        raise HTTPException(
            status_code=409,
            detail=f"Run status is '{run.status}', expected 'paused_hitl'",
        )
    run.status = "failed"
    run.result_json = {"rejected_by": user["user_id"]}
    await session.commit()
    _pub(str(run_id), {"event": "workflow_rejected"})
    logger.info("workflow_run_rejected", run_id=str(run_id), user_id=user["user_id"])
    return WorkflowRunResponse.model_validate(run)
```

**Important:** The `/runs/{run_id}/events`, `/runs/{run_id}/approve`, and `/runs/{run_id}/reject` routes must be registered **before** `/{workflow_id}` in the router file — FastAPI matches routes top-to-bottom and `runs` would otherwise be captured as a `workflow_id` UUID.

**Step 4: Run tests**

```bash
cd backend && .venv/bin/pytest tests/test_workflows_run_api.py -v
```
Expected: 4 tests PASS

**Step 5: Commit**

```bash
git add backend/api/routes/workflows.py backend/tests/test_workflows_run_api.py
git commit -m "feat(04-03): add run, SSE stream, approve, and reject endpoints"
```

---

## Task 5: Cron Trigger Scheduler

**Files:**
- Create: `backend/scheduler/tasks/cron_trigger.py`
- Modify: `backend/scheduler/celery_app.py`
- Test: `backend/tests/scheduler/test_cron_trigger.py`

**Step 1: Install `croniter`**

```bash
cd backend && uv add croniter
```

**Step 2: Write failing tests**

```python
# backend/tests/scheduler/test_cron_trigger.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_fire_cron_triggers_creates_run_for_due_trigger():
    """A trigger due within the last 60s creates a WorkflowRun and enqueues execution."""
    trigger = MagicMock()
    trigger.id = uuid4()
    trigger.workflow_id = uuid4()
    trigger.owner_user_id = uuid4()
    trigger.cron_expression = "* * * * *"  # every minute — always due

    mock_run = MagicMock()
    mock_run.id = uuid4()

    with patch("scheduler.tasks.cron_trigger.async_session") as mock_sf, \
         patch("scheduler.tasks.cron_trigger.execute_workflow_task") as mock_exec:

        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[trigger]))
                )
            )
        )
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", uuid4()))

        from scheduler.tasks.cron_trigger import fire_cron_triggers
        await fire_cron_triggers()

        mock_session.add.assert_called_once()
        mock_exec.delay.assert_called_once()


@pytest.mark.asyncio
async def test_fire_cron_triggers_skips_trigger_with_no_expression():
    """Triggers with null cron_expression are skipped silently."""
    trigger = MagicMock()
    trigger.id = uuid4()
    trigger.workflow_id = uuid4()
    trigger.owner_user_id = uuid4()
    trigger.cron_expression = None  # No expression

    with patch("scheduler.tasks.cron_trigger.async_session") as mock_sf, \
         patch("scheduler.tasks.cron_trigger.execute_workflow_task") as mock_exec:

        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[trigger]))
                )
            )
        )

        from scheduler.tasks.cron_trigger import fire_cron_triggers
        await fire_cron_triggers()

        mock_exec.delay.assert_not_called()


@pytest.mark.asyncio
async def test_fire_cron_triggers_bad_expression_logs_and_continues():
    """Invalid cron expressions are logged and do not crash the scheduler."""
    trigger = MagicMock()
    trigger.id = uuid4()
    trigger.workflow_id = uuid4()
    trigger.owner_user_id = uuid4()
    trigger.cron_expression = "not-a-cron"

    with patch("scheduler.tasks.cron_trigger.async_session") as mock_sf, \
         patch("scheduler.tasks.cron_trigger.execute_workflow_task") as mock_exec:

        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[trigger]))
                )
            )
        )

        from scheduler.tasks.cron_trigger import fire_cron_triggers
        await fire_cron_triggers()  # must not raise

        mock_exec.delay.assert_not_called()
```

**Step 3: Run to verify they fail**

```bash
cd backend && .venv/bin/pytest tests/scheduler/test_cron_trigger.py -v
```
Expected: `ImportError: No module named 'scheduler.tasks.cron_trigger'`

**Step 4: Create `backend/scheduler/tasks/cron_trigger.py`**

```python
"""
Celery beat task: fire cron-triggered workflows.

fire_cron_triggers_task(): Celery task, runs every 60 seconds via beat.
fire_cron_triggers():       Async logic — loads all active cron triggers,
                            checks if each is due within the last 60s,
                            creates a WorkflowRun and enqueues execution.

Tolerance window: 60 seconds. Celery beat fires every 60s; a trigger is
"due" if its previous scheduled run was within the last 60s.
This prevents double-firing if beat fires a few seconds late.

Security: WorkflowRun.owner_user_id is set to the trigger's owner_user_id.
The execution task (execute_workflow_task) runs as that user — full ACL applies.
"""
import asyncio
from datetime import datetime, timezone

import structlog
from croniter import croniter
from sqlalchemy import select

from core.db import async_session
from core.models.workflow import WorkflowRun, WorkflowTrigger
from scheduler.celery_app import celery_app
from scheduler.tasks.workflow_execution import execute_workflow_task

logger = structlog.get_logger(__name__)

_TOLERANCE_SECONDS = 60


@celery_app.task(
    name="scheduler.tasks.cron_trigger.fire_cron_triggers_task",
    queue="default",
)
def fire_cron_triggers_task() -> None:
    """Celery beat entry point — runs every 60 seconds."""
    asyncio.run(fire_cron_triggers())


async def fire_cron_triggers() -> None:
    """Load and fire all due cron triggers."""
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        result = await session.execute(
            select(WorkflowTrigger)
            .where(WorkflowTrigger.trigger_type == "cron")
            .where(WorkflowTrigger.is_active == True)  # noqa: E712
        )
        triggers = result.scalars().all()

        for trigger in triggers:
            if not trigger.cron_expression:
                continue

            try:
                cron = croniter(trigger.cron_expression, now)
                prev: datetime = cron.get_prev(datetime)
                # croniter returns a naive datetime — make it UTC-aware
                if prev.tzinfo is None:
                    prev = prev.replace(tzinfo=timezone.utc)
                seconds_since_last = (now - prev).total_seconds()

                if seconds_since_last > _TOLERANCE_SECONDS:
                    continue  # Not due yet

                run = WorkflowRun(
                    workflow_id=trigger.workflow_id,
                    owner_user_id=trigger.owner_user_id,
                    trigger_type="cron",
                    status="pending",
                )
                session.add(run)
                await session.commit()
                await session.refresh(run)

                execute_workflow_task.delay(str(run.id))
                logger.info(
                    "cron_trigger_fired",
                    trigger_id=str(trigger.id),
                    run_id=str(run.id),
                    cron=trigger.cron_expression,
                )

            except Exception as exc:
                logger.error(
                    "cron_trigger_error",
                    trigger_id=str(trigger.id),
                    cron=trigger.cron_expression,
                    error=str(exc),
                )
                # Continue processing other triggers
```

**Step 5: Register beat schedule in `backend/scheduler/celery_app.py`**

Add after `celery_app.conf.update(...)`:

```python
celery_app.conf.beat_schedule = {
    "fire-cron-triggers-every-minute": {
        "task": "scheduler.tasks.cron_trigger.fire_cron_triggers_task",
        "schedule": 60.0,  # seconds
    },
}
```

**Step 6: Run tests**

```bash
cd backend && .venv/bin/pytest tests/scheduler/test_cron_trigger.py -v
```
Expected: 3 tests PASS

**Step 7: Commit**

```bash
git add backend/scheduler/tasks/cron_trigger.py backend/scheduler/celery_app.py backend/tests/scheduler/test_cron_trigger.py
git commit -m "feat(04-03): add cron trigger Celery beat scheduler"
```

---

## Task 6: Full Test Run

**Step 1: Run all backend tests**

```bash
cd backend && .venv/bin/pytest tests/ -v --tb=short 2>&1 | tail -40
```
Expected: All tests pass, 0 failures.

**Common issues and fixes:**

**`Import error: No module named 'workflow_events'`**
The `workflow_events.py` lives in `backend/` root. If PYTHONPATH is `backend/`, the import is `from workflow_events import ...`. Verify `backend/pyproject.toml` has `pythonpath = ["."]` in pytest config (it does).

**`AttributeError: module 'redis' has no attribute 'asyncio'`**
Redis async support needs `redis[asyncio]`. Run:
```bash
cd backend && uv add "redis[asyncio]"
```

**`ImportError: cannot import name 'GraphInterrupt'`**
LangGraph's interrupt exception class may have a different path. Check:
```bash
cd backend && .venv/bin/python -c "import langgraph.errors; print(dir(langgraph.errors))"
```
Update the `"Interrupt" in exc_type` check in `execute_workflow` if the class name differs.

**Route ordering conflict (`/runs/...` captured as `/{workflow_id}`)**
If `/api/workflows/runs/pending-hitl` returns 404, the `runs` prefix is being matched as a UUID. Ensure `pending-hitl`, `{run_id}/events`, `{run_id}/approve`, `{run_id}/reject` routes are **above** `/{workflow_id}` in `workflows.py`.

**Step 2: Frontend build check**

```bash
cd frontend && pnpm run build 2>&1 | tail -10
```
Expected: ✓ Compiled successfully

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix(04-03): address issues found during full test run"
```

---

**Plan 04-03 complete.** Delivers:
- Real MCP tool execution in `tool_node` handler — 3 tests
- Redis pub/sub event bus (`workflow_events.py`) — 2 tests
- `execute_workflow` Celery task with SSE event publishing — 2 tests
- Run + SSE stream + approve + reject endpoints — 4 tests
- Cron trigger Celery beat scheduler — 3 tests

**Next: Plan 04-04** — HITL approval with `AsyncPostgresSaver` + canvas status overlay (node renderers, `use-workflow-run` hook, approve/reject buttons in canvas).
