"""TDD tests for calendar sub-agent node."""
import json

import pytest
from langchain_core.messages import HumanMessage


@pytest.mark.asyncio
async def test_calendar_agent_node_returns_calendar_output() -> None:
    from agents.subagents.calendar_agent import calendar_agent_node
    from core.schemas.agent_outputs import CalendarOutput

    state = {
        "messages": [HumanMessage(content="what's on my calendar?")],
        "delivery_targets": ["WEB_CHAT"],
        "loaded_facts": [],
    }
    result = await calendar_agent_node(state)
    parsed = json.loads(result["messages"][0].content)
    output = CalendarOutput.model_validate(parsed)
    assert output.agent == "calendar"
    assert isinstance(output.events, list)


@pytest.mark.asyncio
async def test_calendar_agent_shows_conflict_when_events_overlap() -> None:
    from agents.subagents.calendar_agent import calendar_agent_node

    state = {"messages": [], "delivery_targets": ["WEB_CHAT"], "loaded_facts": []}
    result = await calendar_agent_node(state)
    parsed = json.loads(result["messages"][0].content)
    conflict_events = [e for e in parsed["events"] if e["has_conflict"]]
    assert len(conflict_events) >= 1  # mock data has a conflict


@pytest.mark.asyncio
async def test_calendar_agent_output_has_date() -> None:
    """CalendarOutput.date is a non-empty ISO date string."""
    from agents.subagents.calendar_agent import calendar_agent_node

    state = {"messages": [], "delivery_targets": ["WEB_CHAT"], "loaded_facts": []}
    result = await calendar_agent_node(state)
    parsed = json.loads(result["messages"][0].content)
    assert len(parsed["date"]) == 10  # "YYYY-MM-DD"
