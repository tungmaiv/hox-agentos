"""
Smoke tests verifying sub-agent JSON output validates against Pydantic schemas.

These tests verify:
  1. email_agent_node produces valid EmailSummaryOutput JSON
  2. calendar_agent_node produces JSON with agent="calendar"
  3. ProjectStatusResult schema validates a well-formed dict

They do NOT test MCP calls (those require a running mcp-crm server).
The email and calendar agents use mock data in Phase 3 so no external deps needed.
"""
import json

import pytest


@pytest.mark.asyncio
async def test_email_agent_output_is_valid_json() -> None:
    """email_agent_node must return a valid EmailSummaryOutput JSON-encoded AIMessage."""
    from agents.subagents.email_agent import email_agent_node
    from core.schemas.agent_outputs import EmailSummaryOutput

    state = {
        "messages": [],
        "delivery_targets": ["WEB_CHAT"],
        "loaded_facts": [],
    }
    result = await email_agent_node(state)
    messages = result["messages"]
    assert len(messages) == 1, "email_agent_node must produce exactly one message"
    content = messages[0].content
    parsed = json.loads(content)  # must not raise — valid JSON required
    output = EmailSummaryOutput.model_validate(parsed)
    assert output.agent == "email"
    assert isinstance(output.unread_count, int)
    assert isinstance(output.items, list)


@pytest.mark.asyncio
async def test_calendar_agent_output_has_correct_agent_field() -> None:
    """calendar_agent_node must return JSON with agent='calendar'."""
    from agents.subagents.calendar_agent import calendar_agent_node

    state = {
        "messages": [],
        "delivery_targets": ["WEB_CHAT"],
        "loaded_facts": [],
    }
    result = await calendar_agent_node(state)
    messages = result["messages"]
    assert len(messages) == 1, "calendar_agent_node must produce exactly one message"
    parsed = json.loads(messages[0].content)
    assert parsed["agent"] == "calendar"
    assert "date" in parsed
    assert "events" in parsed


def test_project_status_result_validates_against_schema() -> None:
    """ProjectStatusResult Pydantic schema must accept a well-formed dict."""
    from core.schemas.agent_outputs import ProjectStatusResult

    data = {
        "agent": "project",
        "project_name": "Project Alpha",
        "status": "active",
        "owner": "tung@blitz.local",
        "progress_pct": 65,
        "last_update": "2026-02-25",
    }
    result = ProjectStatusResult.model_validate(data)
    assert result.progress_pct == 65
    assert result.project_name == "Project Alpha"
    assert result.status == "active"
