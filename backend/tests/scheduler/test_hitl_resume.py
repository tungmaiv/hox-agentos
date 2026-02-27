"""
Tests for HITL resume path in execute_workflow.

Validates that when hitl_result is not None (resume path), execute_workflow:
1. Re-compiles the graph with AsyncPostgresSaver
2. Calls aupdate_state() to inject hitl_result into saved checkpoint
3. Re-invokes the graph with None input (continues from checkpoint)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


async def _aiter(items):
    for item in items:
        yield item


@pytest.mark.asyncio
async def test_execute_workflow_with_hitl_result_calls_update_state():
    """
    When hitl_result is not None (resume path), the execution task must:
    1. Re-compile the graph with AsyncPostgresSaver
    2. Call aupdate_state() to inject hitl_result into saved checkpoint
    3. Re-invoke the graph with None input (continues from checkpoint)
    """
    run_id = str(uuid4())

    mock_run = MagicMock()
    mock_run.id = uuid4()
    mock_run.workflow_id = uuid4()
    mock_run.owner_user_id = uuid4()
    mock_run.status = "paused_hitl"
    mock_run.checkpoint_id = run_id

    mock_workflow = MagicMock()
    mock_workflow.definition_json = {
        "schema_version": "1.0",
        "nodes": [],
        "edges": [],
    }

    mock_compiled = AsyncMock()
    mock_compiled.aupdate_state = AsyncMock()
    mock_compiled.astream_events = AsyncMock(return_value=_aiter([]))

    mock_checkpointer = AsyncMock()
    mock_checkpointer.__aenter__ = AsyncMock(return_value=mock_checkpointer)
    mock_checkpointer.__aexit__ = AsyncMock(return_value=False)
    mock_checkpointer.setup = AsyncMock()

    with patch("scheduler.tasks.workflow_execution.async_session") as mock_sf, \
         patch("scheduler.tasks.workflow_execution.compile_workflow_to_stategraph") as mock_compile, \
         patch("scheduler.tasks.workflow_execution.AsyncPostgresSaver") as mock_pg_cls, \
         patch("scheduler.tasks.workflow_execution.publish_event"):

        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(side_effect=[
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_run)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_workflow)),
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_run)),
        ])
        mock_session.commit = AsyncMock()

        mock_builder = MagicMock()
        mock_builder.compile = MagicMock(return_value=mock_compiled)
        mock_compile.return_value = mock_builder
        mock_pg_cls.from_conn_string = MagicMock(return_value=mock_checkpointer)

        from scheduler.tasks.workflow_execution import execute_workflow
        await execute_workflow(run_id, hitl_result="approved")

        # aupdate_state must be called with hitl_result="approved"
        mock_compiled.aupdate_state.assert_called_once()
        update_call_args = mock_compiled.aupdate_state.call_args
        updated_state = update_call_args[0][1]  # second positional arg is the state dict
        assert updated_state.get("hitl_result") == "approved"
