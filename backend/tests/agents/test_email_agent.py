"""TDD tests for email sub-agent node."""
import json

import pytest
from langchain_core.messages import HumanMessage


@pytest.mark.asyncio
async def test_email_agent_node_returns_email_output() -> None:
    from agents.subagents.email_agent import email_agent_node
    from core.schemas.agent_outputs import EmailSummaryOutput

    state = {
        "messages": [HumanMessage(content="summarize my emails")],
        "delivery_targets": ["WEB_CHAT"],
        "loaded_facts": [],
    }
    result = await email_agent_node(state)

    messages = result["messages"]
    assert len(messages) == 1
    content = messages[0].content
    parsed = json.loads(content)
    output = EmailSummaryOutput.model_validate(parsed)
    assert output.agent == "email"


@pytest.mark.asyncio
async def test_email_agent_output_has_unread_count() -> None:
    from agents.subagents.email_agent import email_agent_node

    state = {"messages": [], "delivery_targets": ["WEB_CHAT"], "loaded_facts": []}
    result = await email_agent_node(state)
    parsed = json.loads(result["messages"][0].content)
    assert parsed["unread_count"] >= 0


@pytest.mark.asyncio
async def test_email_agent_output_items_are_email_summary_items() -> None:
    """All items in output match EmailSummaryItem schema."""
    from agents.subagents.email_agent import email_agent_node
    from core.schemas.agent_outputs import EmailSummaryItem

    state = {"messages": [], "delivery_targets": ["WEB_CHAT"], "loaded_facts": []}
    result = await email_agent_node(state)
    parsed = json.loads(result["messages"][0].content)
    for item in parsed["items"]:
        validated = EmailSummaryItem.model_validate(item)
        assert validated.from_ is not None
        assert validated.subject is not None
