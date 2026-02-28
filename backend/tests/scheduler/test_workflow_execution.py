"""
Tests for the execute_workflow Celery task.

Verifies:
- Missing WorkflowRun exits silently without publishing events
- Compiler failure sets run.status = 'failed' and publishes workflow_failed
- Fresh Keycloak roles are fetched before workflow execution
- Keycloak failure fails the workflow run (security-first)
- workflow_name is passed through initial_state
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import uuid4

import httpx


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
    mock_workflow.name = "Test Workflow"

    with patch("scheduler.tasks.workflow_execution.async_session") as mock_sf, \
         patch("scheduler.tasks.workflow_execution.publish_event") as mock_pub, \
         patch("scheduler.tasks.workflow_execution.fetch_user_realm_roles", new_callable=AsyncMock, return_value=["employee"]):

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


# ── Keycloak role fetch tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_workflow_fetches_keycloak_roles():
    """Workflow execution fetches fresh roles from Keycloak (not stale owner_roles_json)."""
    run_id = str(uuid4())
    owner_id = uuid4()

    mock_run = MagicMock()
    mock_run.id = uuid4()
    mock_run.workflow_id = uuid4()
    mock_run.owner_user_id = owner_id
    mock_run.owner_roles_json = ["employee"]  # stale
    mock_run.status = "pending"

    mock_workflow = MagicMock()
    mock_workflow.definition_json = {
        "schema_version": "1.0",
        "nodes": [{"id": "trigger_1", "type": "trigger_node", "data": {}}],
        "edges": [],
    }
    mock_workflow.name = "Test"

    with patch("scheduler.tasks.workflow_execution.async_session") as mock_sf, \
         patch("scheduler.tasks.workflow_execution.publish_event"), \
         patch("scheduler.tasks.workflow_execution.fetch_user_realm_roles", new_callable=AsyncMock, return_value=["employee", "it-admin"]) as mock_fetch, \
         patch("scheduler.tasks.workflow_execution.compile_workflow_to_stategraph") as mock_compile:

        # Make the compiler raise so we don't need to mock the entire graph execution
        mock_compile.side_effect = ValueError("stop here")

        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_run)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_workflow)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_run)),  # for compile failure path
        ])
        mock_session.commit = AsyncMock()

        from scheduler.tasks.workflow_execution import execute_workflow
        await execute_workflow(run_id)

        # Verify fetch_user_realm_roles was called with the owner's user_id
        mock_fetch.assert_called_once_with(str(owner_id))

        # Verify compile was called (roles were resolved successfully before compile)
        mock_compile.assert_called_once()

        # Verify user_context passed to compile_workflow_to_stategraph has fresh roles
        compile_call_args = mock_compile.call_args[0]
        user_context = compile_call_args[1]
        assert user_context["roles"] == ["employee", "it-admin"]


@pytest.mark.asyncio
async def test_execute_workflow_keycloak_failure_sets_failed():
    """Keycloak unreachable fails the workflow run (security-first)."""
    run_id = str(uuid4())

    mock_run = MagicMock()
    mock_run.id = uuid4()
    mock_run.workflow_id = uuid4()
    mock_run.owner_user_id = uuid4()
    mock_run.status = "pending"

    mock_workflow = MagicMock()
    mock_workflow.definition_json = {"schema_version": "1.0", "nodes": [], "edges": []}
    mock_workflow.name = "Failing Workflow"

    with patch("scheduler.tasks.workflow_execution.async_session") as mock_sf, \
         patch("scheduler.tasks.workflow_execution.publish_event") as mock_pub, \
         patch("scheduler.tasks.workflow_execution.fetch_user_realm_roles", new_callable=AsyncMock, side_effect=httpx.ConnectError("unreachable")):

        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_run)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_workflow)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_run)),  # for failure path
        ])
        mock_session.commit = AsyncMock()

        from scheduler.tasks.workflow_execution import execute_workflow
        await execute_workflow(run_id)

        # Status must be failed
        assert mock_run.status == "failed"
        # result_json must contain Keycloak error
        assert "Keycloak role fetch failed" in str(mock_run.result_json)
        # workflow_failed event must be published
        published_events = [c[0][1]["event"] for c in mock_pub.call_args_list]
        assert "workflow_failed" in published_events


@pytest.mark.asyncio
async def test_execute_workflow_passes_workflow_name():
    """Workflow name from DB is included in initial_state passed to graph execution."""
    run_id = str(uuid4())

    mock_run = MagicMock()
    mock_run.id = uuid4()
    mock_run.workflow_id = uuid4()
    mock_run.owner_user_id = uuid4()
    mock_run.status = "pending"

    mock_workflow = MagicMock()
    mock_workflow.definition_json = {
        "schema_version": "1.0",
        "nodes": [{"id": "trigger_1", "type": "trigger_node", "data": {}}],
        "edges": [],
    }
    mock_workflow.name = "Morning Digest"

    # Capture the initial_state passed to astream_events
    captured_state: dict = {}

    async def fake_astream_events(input_state, **kwargs):
        captured_state["input"] = input_state
        return
        yield  # makes this an async generator function

    # Mock compiled graph
    mock_compiled = MagicMock()
    mock_compiled.astream_events = fake_astream_events
    mock_state_snapshot = MagicMock()
    mock_state_snapshot.interrupts = []
    mock_state_snapshot.next = []
    mock_compiled.aget_state = AsyncMock(return_value=mock_state_snapshot)

    # Mock builder returned by compile_workflow_to_stategraph
    mock_builder = MagicMock()
    mock_builder.compile.return_value = mock_compiled

    # Mock AsyncPostgresSaver context manager
    mock_checkpointer = AsyncMock()
    mock_checkpointer.setup = AsyncMock()
    mock_cp_cm = AsyncMock()
    mock_cp_cm.__aenter__ = AsyncMock(return_value=mock_checkpointer)
    mock_cp_cm.__aexit__ = AsyncMock(return_value=False)

    # Mock settings for database URL
    mock_settings = MagicMock()
    mock_settings.database_url = "postgresql+asyncpg://blitz:pw@localhost/blitz"

    with patch("scheduler.tasks.workflow_execution.async_session") as mock_sf, \
         patch("scheduler.tasks.workflow_execution.publish_event"), \
         patch("scheduler.tasks.workflow_execution.fetch_user_realm_roles", new_callable=AsyncMock, return_value=["employee"]), \
         patch("scheduler.tasks.workflow_execution.compile_workflow_to_stategraph", return_value=mock_builder), \
         patch("scheduler.tasks.workflow_execution.AsyncPostgresSaver") as mock_saver_cls, \
         patch("scheduler.tasks.workflow_execution.get_settings", return_value=mock_settings):

        mock_saver_cls.from_conn_string.return_value = mock_cp_cm

        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_run)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_workflow)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_run)),  # final status update
        ])
        mock_session.commit = AsyncMock()

        from scheduler.tasks.workflow_execution import execute_workflow
        await execute_workflow(run_id)

        # Verify workflow_name is in the initial_state passed to the graph
        assert "input" in captured_state, "astream_events was never called"
        assert captured_state["input"]["workflow_name"] == "Morning Digest"
