"""
Workflow execution Celery task.

execute_workflow_task(run_id_str):  Celery entry point (sync wrapper).
execute_workflow(run_id_str):       Main async execution logic.

Execution flow:
  1. Load WorkflowRun + Workflow from DB
  2. Build UserContext from run.owner_user_id
  3. Set run.status = "running", commit
  4. compile_workflow_to_stategraph(definition_json, user_context)
  5. Compile with AsyncPostgresSaver for HITL cross-process persistence
  6. astream_events() — publish SSE events to Redis for each node
  7. On completion: set run.status = "completed", store result_json
  8. On GraphInterrupt (HITL): set run.status = "paused_hitl", publish hitl_paused event
  9. On error: set run.status = "failed", publish workflow_failed event

Resume path (hitl_result is not None):
  - Re-compile graph with same AsyncPostgresSaver and thread_id
  - await compiled.aupdate_state(config, {"hitl_result": decision})
  - await compiled.astream_events(None, config)  # resumes from checkpoint

Security: Celery workers run as the job owner (WorkflowRun.owner_user_id).
Full 3-gate ACL is enforced inside node handlers (see node_handlers.py).
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import select

from agents.graphs import compile_workflow_to_stategraph
from core.config import get_settings
from core.db import async_session
from core.models.workflow import Workflow, WorkflowRun
from scheduler.celery_app import celery_app
from security.keycloak_client import fetch_user_realm_roles
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
    try:
        await _execute_workflow_inner(run_id_str, hitl_result=hitl_result)
    finally:
        # Dispose the shared asyncpg engine after each task so the next
        # asyncio.run() call gets a fresh event loop with clean connections.
        from core.db import engine  # noqa: PLC0415
        await engine.dispose()


async def _execute_workflow_inner(run_id_str: str, hitl_result: str | None = None) -> None:
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
        workflow_name = workflow.name or ""
        run.status = "running"
        await session.commit()

    # ── 1b. Fetch fresh Keycloak roles (security-first: no roles = no execution) ──
    try:
        owner_roles = await fetch_user_realm_roles(str(owner_user_id))
        logger.info("workflow_roles_resolved", run_id=run_id_str, roles=owner_roles)
    except Exception as exc:
        logger.error("workflow_roles_fetch_failed", run_id=run_id_str, error=str(exc))
        async with async_session() as session:
            result = await session.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
            run = result.scalar_one_or_none()
            if run:
                run.status = "failed"
                run.result_json = {"error": f"Keycloak role fetch failed: {exc}"}
                await session.commit()
        publish_event(run_id_str, {"event": "workflow_failed", "error": f"Keycloak unreachable: {exc}"})
        return

    # ── 2. Build user context (runs as job owner) ─────────────────────────────
    user_context: dict[str, Any] = {
        "user_id": str(owner_user_id),
        "email": "",       # Not available in worker — ACL only needs user_id + roles
        "username": "",
        "roles": owner_roles,
        "groups": [],
    }
    user_context["resolved_roles"] = owner_roles  # Audit: log the actual Keycloak roles used

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
    # AsyncPostgresSaver persists graph state to PostgreSQL so a paused workflow
    # can be resumed in a new Celery worker process (HITL cross-process persistence).
    _settings = get_settings()
    # AsyncPostgresSaver uses psycopg3 — strip the +asyncpg driver prefix
    pg_conn_str = _settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

    # Known node IDs from the definition (used to filter astream_events noise)
    known_node_ids: set[str] = {n["id"] for n in definition_json.get("nodes", [])}

    initial_state: dict[str, Any] = {
        "run_id": run_id,
        "user_context": user_context,
        "node_outputs": {},
        "current_output": None,
        "hitl_result": hitl_result,  # None for fresh run, "approved"/"rejected" on resume
        "workflow_name": workflow_name,
    }
    config = {"configurable": {"thread_id": run_id_str}}

    final_output: Any = None

    async with AsyncPostgresSaver.from_conn_string(pg_conn_str) as checkpointer:
        await checkpointer.setup()  # creates LangGraph checkpoint tables if not exist
        compiled = builder.compile(checkpointer=checkpointer)

        if hitl_result is not None:
            # Resume path: inject hitl_result into the saved checkpoint state
            await compiled.aupdate_state(config, {"hitl_result": hitl_result})
            input_state = None  # graph resumes from the saved checkpoint
        else:
            # Fresh execution
            input_state = initial_state

        try:
            async for event in compiled.astream_events(input_state, config=config, version="v1"):
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
            # Genuine error — GraphInterrupt is suppressed by LangGraph 1.0 and
            # never propagates here; HITL is detected via aget_state() below.
            exc_type = type(exc).__name__
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

        # ── LangGraph 1.0 HITL detection ──────────────────────────────────────
        # GraphInterrupt is suppressed internally by the graph runner and never
        # raised to the caller. After astream_events() returns normally, check
        # the saved checkpoint for pending interrupts via aget_state().
        state_snapshot = await compiled.aget_state(config)
        if state_snapshot.interrupts:
            raw_interrupt = state_snapshot.interrupts[0]
            interrupt_data: dict[str, Any] = (
                raw_interrupt.value
                if isinstance(raw_interrupt.value, dict)
                else {"data": raw_interrupt.value}
            )
            message = interrupt_data.get("message", "Approval required to continue.")
            hitl_node_id = state_snapshot.next[0] if state_snapshot.next else None

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
                "node_id": hitl_node_id,
                "message": message,
                "interrupt_data": interrupt_data,
            })
            logger.info("workflow_paused_hitl", run_id=run_id_str, message=message)
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
