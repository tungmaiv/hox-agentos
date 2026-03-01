"""
User-facing tool API — list tools available to the current user.

GET    /api/tools             — list tools visible to the current user (filtered by role permissions)

Security:
  - Requires 'chat' permission (basic user access via Gate 2 RBAC)
  - Tool visibility filtered by artifact_permissions (role-level) and user_artifact_permissions (per-user)
  - Only active tools (status='active' AND is_active=True) are returned
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.tool_definition import ToolDefinition
from core.models.user import UserContext
from core.schemas.registry import ToolListItem
from security.deps import get_current_user, get_user_db
from security.rbac import batch_check_artifact_permissions, has_permission

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])


async def _require_chat(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> UserContext:
    """Gate 2 dependency: require 'chat' permission."""
    if not await has_permission(user, "chat", session):
        raise HTTPException(status_code=403, detail="Chat permission required")
    return user


@router.get("")
async def list_user_tools(
    user: UserContext = Depends(_require_chat),
    session: AsyncSession = Depends(get_user_db),
) -> list[ToolListItem]:
    """List tools available to the current user.

    Filters:
    1. Only active tools (status='active' AND is_active=True)
    2. Excludes tools denied by artifact_permissions for user's roles
    3. Respects user_artifact_permissions per-user overrides
    """
    result = await session.execute(
        select(ToolDefinition).where(
            ToolDefinition.status == "active",
            ToolDefinition.is_active == True,  # noqa: E712
        )
    )
    tools = result.scalars().all()

    # Batch permission check: 2 queries instead of N per-tool queries
    all_ids = [tool.id for tool in tools]
    allowed_ids = await batch_check_artifact_permissions(
        user, "tool", all_ids, session
    )
    visible = [
        ToolListItem.model_validate(tool)
        for tool in tools
        if tool.id in allowed_ids
    ]

    logger.info(
        "user_tools_listed",
        user_id=str(user["user_id"]),
        total=len(tools),
        visible=len(visible),
    )
    return visible
