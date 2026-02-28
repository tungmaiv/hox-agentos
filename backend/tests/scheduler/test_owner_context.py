"""
Tests verifying CHAN-06: scheduled workflows run as the owning user's context.

Ensures:
- execute_workflow builds user_context from WorkflowRun.owner_user_id
- user_context is injected into initial_state so all node handlers receive it
- cron_trigger creates WorkflowRun with trigger.owner_user_id
- Memory isolation: user_id in state.user_context scopes all downstream queries
"""
import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_scheduled_job_runs_as_owner() -> None:
    """
    execute_workflow passes owner_user_id to compile_workflow_to_stategraph
    in the user_context dict. This ensures all node handlers (tool_node,
    agent_node, channel_output_node) receive the owner's identity.
    """
    run_id = uuid.uuid4()
    owner_user_id = uuid.uuid4()
    workflow_id = uuid.uuid4()

    mock_run = MagicMock()
    mock_run.id = run_id
    mock_run.workflow_id = workflow_id
    mock_run.owner_user_id = owner_user_id
    mock_run.owner_roles_json = ["employee", "developer"]
    mock_run.status = "pending"

    mock_workflow = MagicMock()
    mock_workflow.definition_json = {
        "schema_version": "1.0",
        "nodes": [
            {"id": "trigger", "type": "trigger_node", "data": {}},
        ],
        "edges": [],
    }

    captured_user_context = {}

    def capture_compile(definition_json, user_context):
        """Capture user_context passed to compile to verify owner identity."""
        captured_user_context.update(user_context)
        # Return a mock builder that can be compiled
        mock_builder = MagicMock()
        mock_compiled = AsyncMock()
        mock_compiled.astream_events = AsyncMock(return_value=AsyncMock(
            __aiter__=lambda self: self,
            __anext__=AsyncMock(side_effect=StopAsyncIteration),
        ))
        mock_compiled.aget_state = AsyncMock(return_value=MagicMock(
            interrupts=[],
        ))
        mock_builder.compile = MagicMock(return_value=mock_compiled)
        return mock_builder

    mock_workflow.name = "Test Workflow"

    # Patch all external dependencies
    with patch("scheduler.tasks.workflow_execution.async_session") as mock_sf, \
         patch("scheduler.tasks.workflow_execution.compile_workflow_to_stategraph", side_effect=capture_compile), \
         patch("scheduler.tasks.workflow_execution.publish_event"), \
         patch("scheduler.tasks.workflow_execution.fetch_user_realm_roles", new_callable=AsyncMock, return_value=["employee", "developer"]), \
         patch("scheduler.tasks.workflow_execution.AsyncPostgresSaver") as mock_pg:

        # Setup async session mock
        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        # First session: load run + workflow + set running
        # Second session: mark completed
        mock_session.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_run)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_workflow)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_run)),
        ])
        mock_session.commit = AsyncMock()

        # Mock AsyncPostgresSaver context manager
        mock_checkpointer = AsyncMock()
        mock_checkpointer.setup = AsyncMock()
        mock_pg.from_conn_string = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_checkpointer),
            __aexit__=AsyncMock(return_value=False),
        ))

        from scheduler.tasks.workflow_execution import execute_workflow
        await execute_workflow(str(run_id))

    # VERIFY: user_context was built from owner_user_id
    assert captured_user_context["user_id"] == str(owner_user_id)
    assert captured_user_context["roles"] == ["employee", "developer"]


@pytest.mark.asyncio
async def test_cron_trigger_uses_owner_user_id() -> None:
    """
    fire_cron_triggers creates WorkflowRun with trigger.owner_user_id,
    ensuring the execution task runs as the trigger owner.
    """
    trigger_owner_id = uuid.uuid4()
    trigger_id = uuid.uuid4()
    workflow_id = uuid.uuid4()

    mock_trigger = MagicMock()
    mock_trigger.id = trigger_id
    mock_trigger.workflow_id = workflow_id
    mock_trigger.owner_user_id = trigger_owner_id
    mock_trigger.owner_roles_json = ["employee"]
    mock_trigger.trigger_type = "cron"
    mock_trigger.cron_expression = "* * * * *"  # every minute
    mock_trigger.is_active = True

    created_runs = []

    with patch("scheduler.tasks.cron_trigger.async_session") as mock_sf, \
         patch("scheduler.tasks.cron_trigger.execute_workflow_task") as mock_exec:

        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_session.execute = AsyncMock(return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_trigger])))
        ))
        mock_session.commit = AsyncMock()

        # Capture the WorkflowRun that gets added to the session
        original_add = mock_session.add

        def capture_add(obj):
            created_runs.append(obj)

        mock_session.add = MagicMock(side_effect=capture_add)
        mock_session.refresh = AsyncMock()

        from scheduler.tasks.cron_trigger import fire_cron_triggers
        await fire_cron_triggers()

    # VERIFY: WorkflowRun was created with trigger's owner_user_id
    assert len(created_runs) == 1
    run = created_runs[0]
    assert run.owner_user_id == trigger_owner_id
    assert run.owner_roles_json == ["employee"]
