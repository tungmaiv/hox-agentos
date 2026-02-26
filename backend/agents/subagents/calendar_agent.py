"""
Calendar sub-agent node. Phase 3: returns mock data with conflict detection.
"""
from datetime import date

import structlog
from langchain_core.messages import AIMessage

from agents.state.types import BlitzState
from core.schemas.agent_outputs import CalendarEvent, CalendarOutput

logger = structlog.get_logger(__name__)

_MOCK_EVENTS: list[CalendarEvent] = [
    CalendarEvent(
        title="Team Standup",
        start_time="2026-02-26T09:00:00Z",
        end_time="2026-02-26T09:15:00Z",
        location="Zoom",
        has_conflict=False,
    ),
    CalendarEvent(
        title="Architecture Review",
        start_time="2026-02-26T10:00:00Z",
        end_time="2026-02-26T11:00:00Z",
        location="Conference Room B",
        has_conflict=False,
    ),
    CalendarEvent(
        title="1:1 with PM",
        start_time="2026-02-26T10:30:00Z",
        end_time="2026-02-26T11:00:00Z",
        location="Zoom",
        has_conflict=True,
    ),
    CalendarEvent(
        title="Sprint Demo",
        start_time="2026-02-26T14:00:00Z",
        end_time="2026-02-26T15:00:00Z",
        location="Main Conference Room",
        has_conflict=False,
    ),
]


async def calendar_agent_node(state: BlitzState) -> dict:
    """
    Calendar sub-agent. Returns mock CalendarOutput as JSON-encoded AIMessage.
    has_conflict=True on events with overlapping time ranges (pre-computed in mock).
    """
    logger.info("calendar_agent_invoked")
    today = date.today().isoformat()
    output = CalendarOutput(date=today, events=_MOCK_EVENTS)
    ai_message = AIMessage(content=output.model_dump_json())
    return {"messages": [ai_message]}
