"""
WorkflowState — shared state TypedDict for workflow execution graphs.

Separate from BlitzState (which is for conversational agents).
Workflows are not conversations — they have no message history.

Fields:
  run_id:         UUID of the WorkflowRun DB row (for status updates).
  user_context:   Owner's identity dict from JWT (user_id, roles, email, etc).
                  Set by the Celery worker from WorkflowRun.owner_user_id.
                  Enforces per-user memory isolation and 3-gate ACL.
  node_outputs:   Accumulated outputs keyed by node_id. Every node appends its
                  result here so downstream nodes can reference prior outputs.
  current_output: Output of the most recently completed node. Condition nodes
                  evaluate expressions against this value.
  hitl_result:    Set to "approved" or "rejected" when resuming after interrupt().
                  None during normal forward execution.
"""
import uuid
from typing import Any

from typing_extensions import TypedDict


class WorkflowState(TypedDict):
    run_id: uuid.UUID | None
    user_context: dict[str, Any] | None
    node_outputs: dict[str, Any]   # keyed by node_id
    current_output: Any            # output of the last completed node
    hitl_result: str | None        # "approved" | "rejected" | None
