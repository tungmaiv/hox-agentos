"""Tests for SkillHandler."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_skill_handler_forces_draft_when_tool_gaps_present():
    """on_create must override status to 'draft' when config.tool_gaps is non-empty."""
    from registry.handlers.skill_handler import SkillHandler

    handler = SkillHandler()
    entry = MagicMock()
    entry.name = "test-skill"
    entry.status = "active"  # admin tried to save as active
    entry.config = {
        "skill_type": "procedural",
        "procedure_json": {"steps": []},
        "tool_gaps": [{"intent": "send slack", "tool": "MISSING:send-slack"}],
    }
    session = AsyncMock()

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(
            "registry.handlers.skill_handler.scan_skill_with_fallback",
            AsyncMock(return_value={"score": 100}),
            raising=False,
        )
        await handler.on_create(entry, session)

    assert entry.status == "draft", "status must be forced to draft when gaps present"


@pytest.mark.asyncio
async def test_skill_handler_does_not_force_draft_when_no_gaps():
    """on_create must not change status when tool_gaps is empty."""
    from registry.handlers.skill_handler import SkillHandler

    handler = SkillHandler()
    entry = MagicMock()
    entry.name = "clean-skill"
    entry.status = "active"
    entry.config = {
        "skill_type": "procedural",
        "procedure_json": {"steps": []},
        "tool_gaps": [],
    }
    session = AsyncMock()

    # scan_skill_with_fallback may or may not be called — no need to mock for this test
    await handler.on_create(entry, session)

    assert entry.status == "active", "status must not be changed when no gaps"
