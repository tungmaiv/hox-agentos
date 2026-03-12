"""Tests for ToolHandler gap auto-resolution."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_tool_handler_resolves_matching_skill_gap():
    """on_create promotes draft skill to pending_activation when its gap matches new tool."""
    from registry.handlers.tool_handler import ToolHandler

    handler = ToolHandler()

    # New tool being created
    new_tool = MagicMock()
    new_tool.name = "slack.send-message"

    # Draft skill with a matching gap
    skill_entry = MagicMock()
    skill_entry.id = "skill-uuid-1"
    skill_entry.name = "daily-standup"
    skill_entry.status = "draft"
    skill_entry.config = {
        "skill_type": "procedural",
        "tool_gaps": [
            {"intent": "send Slack message", "tool": "MISSING:slack-send-message"}
        ],
    }

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [skill_entry]

    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=mock_result)

    await handler.on_create(new_tool, session)

    assert skill_entry.status == "pending_activation", (
        "skill must be promoted to pending_activation when gap is resolved"
    )
    assert skill_entry.config["tool_gaps"] == [], (
        "tool_gaps must be cleared after resolution"
    )
    session.add.assert_called_with(skill_entry)


@pytest.mark.asyncio
async def test_tool_handler_does_not_promote_skill_with_remaining_gaps():
    """on_create must not promote skill if other gaps remain after partial resolution."""
    from registry.handlers.tool_handler import ToolHandler

    handler = ToolHandler()

    new_tool = MagicMock()
    new_tool.name = "slack.send-message"

    skill_entry = MagicMock()
    skill_entry.id = "skill-uuid-2"
    skill_entry.name = "complex-skill"
    skill_entry.status = "draft"
    skill_entry.config = {
        "tool_gaps": [
            {"intent": "send Slack", "tool": "MISSING:slack-send-message"},
            {"intent": "post to Teams", "tool": "MISSING:teams-post-message"},  # still missing
        ],
    }

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [skill_entry]

    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=mock_result)

    await handler.on_create(new_tool, session)

    assert skill_entry.status == "draft", "status must stay draft when gaps remain"
    assert len(skill_entry.config["tool_gaps"]) == 1, "only the resolved gap must be removed"


@pytest.mark.asyncio
async def test_tool_handler_gap_resolution_survives_db_error():
    """on_create must not crash when gap resolution DB query fails."""
    from registry.handlers.tool_handler import ToolHandler

    handler = ToolHandler()
    new_tool = MagicMock()
    new_tool.name = "some.tool"

    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock(side_effect=Exception("DB error"))

    # Must not raise
    await handler.on_create(new_tool, session)
