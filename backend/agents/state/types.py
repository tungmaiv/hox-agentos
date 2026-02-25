# backend/agents/state/types.py
"""
BlitzState — shared state TypedDict for all Blitz AgentOS LangGraph graphs.

Passed between graph nodes. Never returned to the frontend directly.
The add_messages reducer means nodes return partial state: {"messages": [new_msg]}
and LangGraph appends new_msg to the existing messages list automatically.

Evolution:
  Phase 2: messages only (conversational chat)
  Phase 3: add user_id, conversation_id, loaded_memory fields
  Phase 4: add workflow_id, workflow_step for canvas execution
"""
from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class BlitzState(TypedDict):
    """Shared state for all Blitz AgentOS LangGraph graphs."""

    messages: Annotated[list[BaseMessage], add_messages]
