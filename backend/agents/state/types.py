# backend/agents/state/types.py
"""
BlitzState — shared state TypedDict for all Blitz AgentOS LangGraph graphs.

Passed between graph nodes. Never returned to the frontend directly.
The add_messages reducer means nodes return partial state: {"messages": [new_msg]}
and LangGraph appends new_msg to the existing messages list automatically.

Evolution:
  Phase 2: messages + user_id + conversation_id + initial_message_count (memory wired)
  Phase 3: add loaded_facts (long-term memory), delivery_targets (routing placeholder)
  Phase 4: add workflow_id, workflow_step for canvas execution
"""
from typing import Annotated
from uuid import UUID

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class BlitzState(TypedDict):
    """Shared state for all Blitz AgentOS LangGraph graphs."""

    messages: Annotated[list[BaseMessage], add_messages]
    # Set by gateway/runtime.py from JWT + threadId before graph invocation:
    user_id: UUID | None
    conversation_id: UUID | None
    # Number of messages present BEFORE the graph ran — used by save_memory to
    # avoid re-saving history loaded by load_memory (deduplication guard).
    initial_message_count: int
    # Phase 3: long-term memory facts injected by _load_memory_node (for audit/debug).
    # Each string is the content of a MemoryFact returned by semantic search.
    loaded_facts: list[str]
    # Phase 3: delivery targets for DeliveryRouterNode (03-04).
    # Pre-registered here to avoid state schema changes mid-graph.
    # Default: ["WEB_CHAT"]. Extended in Phase 4 (Channels) with channel identifiers.
    delivery_targets: list[str]
