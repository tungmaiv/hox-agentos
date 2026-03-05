"""
Tool ACL Gate 3 — Per-user, per-tool access control and audit logging.

Implements Gate 3 of the 3-gate security system:
  Gate 1: JWT validation (security/jwt.py)
  Gate 2: RBAC permission check (security/rbac.py)
  Gate 3: Tool ACL check (this module) ← you are here

Gate 3 enforces per-user tool overrides that go beyond role-level RBAC.
For example, an employee with tool:email permission can be explicitly denied
email.fetch for their specific user_id via a ToolAcl row.

Policy:
  - No row → default ALLOW (open unless explicitly denied)
  - Row with allowed=False → DENY
  - Row with allowed=True → ALLOW (explicit allowlist override)

Security invariant:
  user_id MUST come from get_current_user() (JWT Gate 1).
  It MUST NOT be accepted from request body, query params, or user input.

Audit invariant:
  Every tool call attempt is logged via get_audit_logger().
  The log entry contains ONLY: user_id, tool name, allowed decision, duration_ms.
  Credentials (access_token, refresh_token, password) are NEVER logged.
"""
import time
from uuid import UUID

import structlog
from cachetools import TTLCache
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_audit_logger
from core.metrics import blitz_tool_calls_total, blitz_tool_duration_seconds
from core.models.tool_acl import ToolAcl

logger = structlog.get_logger(__name__)
audit_logger = get_audit_logger()


async def check_tool_acl(
    user_id: UUID,
    tool_name: str,
    session: AsyncSession,
) -> bool:
    """
    Gate 3: Check per-user Tool ACL.

    Queries the tool_acl table for an explicit allow/deny row for this
    (user_id, tool_name) pair. Returns True (allow) by default when no row exists.

    Args:
        user_id: UUID from JWT sub claim (via get_current_user — not request body).
        tool_name: Name of the tool being invoked (e.g. "email.fetch").
        session: Async SQLAlchemy session (from get_db() dependency).

    Returns:
        True if the tool call is allowed, False if explicitly denied.
    """
    result = await session.execute(
        select(ToolAcl).where(
            ToolAcl.user_id == user_id,
            ToolAcl.tool_name == tool_name,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return True  # default allow — no explicit policy set
    return row.allowed


# Tool ACL result cache — 60s TTL, max 500 entries.
# Key: (user_id, tool_name). Safe: user_id from JWT, never from request body.
_acl_cache: TTLCache = TTLCache(maxsize=500, ttl=60)


async def check_tool_acl_cached(
    user_id: UUID,
    tool_name: str,
    session: AsyncSession,
) -> bool:
    """
    Gate 3 with TTL cache: avoids a DB query on every tool call for the same user.

    Cache TTL: 60 seconds. Cache is per-process (not shared across workers).
    Call clear_acl_cache() in tests to reset state between test cases.
    """
    cache_key = (user_id, tool_name)
    if cache_key in _acl_cache:
        return _acl_cache[cache_key]
    result = await check_tool_acl(user_id, tool_name, session)
    _acl_cache[cache_key] = result
    return result


def clear_acl_cache() -> None:
    """Clear the ACL TTL cache. Used in tests."""
    _acl_cache.clear()


async def log_tool_call(
    user_id: UUID,
    tool_name: str,
    allowed: bool,
    duration_ms: int,
) -> None:
    """
    Emit an audit log entry for a tool call attempt.

    This function is fire-and-forget — it must not raise.
    Called after both Gate 2 (RBAC) and Gate 3 (ACL) have been evaluated,
    regardless of the allow/deny outcome.

    Logged fields:
      - event: "tool_call" (constant)
      - user_id: str(UUID) — who invoked the tool
      - tool: str — which tool was invoked
      - allowed: bool — final allow/deny decision
      - duration_ms: int — time from gate entry to decision in milliseconds

    NEVER logged: access_token, refresh_token, password, or any credential value.

    Args:
        user_id: UUID from JWT (never from request body).
        tool_name: Name of the tool being invoked.
        allowed: True if the call was permitted, False if denied.
        duration_ms: Total gate evaluation time in milliseconds.
    """
    audit_logger.info(
        "tool_call",
        user_id=str(user_id),
        tool=tool_name,
        allowed=allowed,
        duration_ms=duration_ms,
    )
    # Prometheus metric increment (alongside existing structlog audit log)
    blitz_tool_calls_total.labels(tool=tool_name, success=str(allowed)).inc()
    blitz_tool_duration_seconds.labels(tool=tool_name).observe(duration_ms / 1000.0)
