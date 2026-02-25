# backend/core/context.py
"""
Shared Python contextvars for passing request-scoped data through async call stacks.

These contextvars allow gateway/runtime.py to set request context (user, conversation)
that graph nodes in agents/master_agent.py can read without threading args through
every function signature.

Usage pattern:
    # In gateway/runtime.py (before graph invocation):
    user_token = current_user_ctx.set(validated_user)
    conv_token = current_conversation_id_ctx.set(conversation_uuid)
    try:
        result = await graph.ainvoke(state)
    finally:
        current_user_ctx.reset(user_token)
        current_conversation_id_ctx.reset(conv_token)

    # In agents/master_agent.py (inside graph nodes):
    try:
        conversation_id = current_conversation_id_ctx.get()
    except LookupError:
        conversation_id = None  # safe fallback for tests
"""
import contextvars
from uuid import UUID

from core.models.user import UserContext

# Set by gateway/runtime.py after JWT validation; read by graph nodes.
current_user_ctx: contextvars.ContextVar[UserContext] = contextvars.ContextVar(
    "current_user_ctx"
)

# Set by gateway/runtime.py by extracting threadId from the CopilotKit request body.
# CopilotKit sends the conversation UUID as threadId in each AG-UI request.
# Graph nodes read this to scope memory operations to the correct conversation.
current_conversation_id_ctx: contextvars.ContextVar[UUID] = contextvars.ContextVar(
    "current_conversation_id_ctx"
)
