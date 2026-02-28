"""
Agent routes — all endpoints enforce the full 3-gate security chain.

Security gates applied in order:
  Gate 1: JWT validation via Depends(get_current_user)
  Gate 2: RBAC permission check via has_permission()
  Gate 3: Tool ACL via check_tool_acl()
  Audit:  log_tool_call() after every gate evaluation

Routes:
  POST /api/agents/chat — Phase 1 stub; returns 501 for authorized users
"""
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.user import UserContext
from core.schemas.common import ErrorResponse
from security.acl import check_tool_acl, log_tool_call
from security.deps import get_current_user
from security.rbac import has_permission

import structlog

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])


@router.post(
    "/chat",
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid JWT"},
        403: {"model": ErrorResponse, "description": "Insufficient permissions"},
        501: {"description": "Chat endpoint not yet implemented (Phase 2)"},
    },
)
async def chat(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """
    Phase 1 stub: validates all 3 security gates and returns 501.
    Full agent implementation in Phase 2.

    Security chain:
      1. Gate 1 (JWT) — enforced by Depends(get_current_user)
      2. Gate 2 (RBAC) — requires 'chat' permission
      3. Gate 3 (Tool ACL) — checks tool_acl table for per-user overrides
    """
    start_ms = int(time.monotonic() * 1000)

    # Gate 2: RBAC — require 'chat' permission
    if not await has_permission(user, "chat", session):
        elapsed = int(time.monotonic() * 1000) - start_ms
        await log_tool_call(user["user_id"], "agents.chat", False, elapsed)
        raise HTTPException(
            status_code=403,
            detail={
                "detail": "Permission denied",
                "permission_required": "chat",
                "user_roles": user["roles"],
                "hint": "Contact IT admin",
            },
        )

    # Gate 3: Tool ACL — check per-user overrides
    allowed = await check_tool_acl(user["user_id"], "agents.chat", session)
    elapsed = int(time.monotonic() * 1000) - start_ms
    await log_tool_call(user["user_id"], "agents.chat", allowed, elapsed)

    if not allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "detail": "Permission denied by ACL",
                "permission_required": "agents.chat",
                "user_roles": user["roles"],
                "hint": "Contact IT admin",
            },
        )

    # Phase 2 will implement the actual agent logic
    raise HTTPException(
        status_code=501,
        detail="Chat not yet implemented — coming in Phase 2",
    )
