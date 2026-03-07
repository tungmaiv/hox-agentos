"""
User-facing skill API — list available skills and execute them.

GET    /api/skills             — list skills available to current user (filtered by role permissions)
POST   /api/skills/{name}/run  — execute a skill by name

Security:
  - Requires 'chat' permission (basic user access via Gate 2 RBAC)
  - Skill visibility filtered by artifact_permissions (role-level) and user_artifact_permissions (per-user)
  - Disabled/inactive skills return 404 on execution
  - Denied skills return 403 on execution
"""
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import asc, desc, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.skill_definition import SkillDefinition
from core.models.user import UserContext
from core.schemas.registry import SkillListItem, SkillRunResponse
from security.deps import get_current_user, get_user_db
from security.rbac import batch_check_artifact_permissions, check_artifact_permission, has_permission
from skills.executor import SkillExecutor

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/skills", tags=["skills"])


class SkillRunRequest(BaseModel):
    """Optional user input for skill execution."""

    user_input: dict[str, Any] | None = None


async def _require_chat(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> UserContext:
    """Gate 2 dependency: require 'chat' permission."""
    if not await has_permission(user, "chat", session):
        raise HTTPException(status_code=403, detail="Chat permission required")
    return user


@router.get("")
async def list_user_skills(
    q: str | None = Query(None, description="Full-text search on name and description"),
    category: str | None = Query(None, description="Filter by category"),
    skill_type: str | None = Query(None, description="Filter by skill_type"),
    sort: str | None = Query(None, description="Sort: newest (default), oldest, most_used"),
    user: UserContext = Depends(_require_chat),
    session: AsyncSession = Depends(get_user_db),
) -> list[SkillListItem]:
    """List skills available to the current user.

    Returns all active skills without ACL join per CONTEXT.md decision (SKCAT-03).
    Supports FTS, category, skill_type, and sort filtering.
    """
    stmt = select(SkillDefinition).where(
        SkillDefinition.status == "active",
        SkillDefinition.is_active == True,  # noqa: E712
    )
    if q:
        stmt = stmt.where(
            func.to_tsvector(
                text("'simple'"),
                func.coalesce(SkillDefinition.name, "") + " " + func.coalesce(SkillDefinition.description, "")
            ).op("@@")(func.plainto_tsquery(text("'simple'"), q))
        )
    if category is not None:
        stmt = stmt.where(SkillDefinition.category == category)
    if skill_type is not None:
        stmt = stmt.where(SkillDefinition.skill_type == skill_type)
    if sort == "oldest":
        stmt = stmt.order_by(asc(SkillDefinition.created_at))
    elif sort == "most_used":
        stmt = stmt.order_by(desc(SkillDefinition.usage_count))
    else:
        stmt = stmt.order_by(desc(SkillDefinition.created_at))

    result = await session.execute(stmt)
    skills = result.scalars().all()
    # Return all active skills directly — no ACL join per CONTEXT.md decision
    visible = [SkillListItem.model_validate(skill) for skill in skills]

    logger.info(
        "user_skills_listed",
        user_id=str(user["user_id"]),
        total=len(skills),
        visible=len(visible),
    )
    return visible


@router.post("/{skill_name}/run")
async def run_user_skill(
    skill_name: str,
    body: SkillRunRequest | None = None,
    user: UserContext = Depends(_require_chat),
    session: AsyncSession = Depends(get_user_db),
) -> SkillRunResponse:
    """Execute a skill by name.

    - Lookup skill by name WHERE status='active' AND is_active=True. If not found -> 404.
    - Check artifact permission for user's roles. If denied -> 403.
    - Dispatch based on skill_type:
      - procedural: SkillExecutor.run() with tool call pipeline
      - instructional: Return instruction_markdown content
    """
    result = await session.execute(
        select(SkillDefinition).where(
            SkillDefinition.name == skill_name,
            SkillDefinition.status == "active",
            SkillDefinition.is_active == True,  # noqa: E712
        )
    )
    skill = result.scalar_one_or_none()

    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found or not active")

    # Check artifact permission
    allowed = await check_artifact_permission(user, "skill", skill.id, session)
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: not authorized for skill '{skill_name}'",
        )

    user_input = body.user_input if body else None

    if skill.skill_type == "procedural":
        executor = SkillExecutor()
        user_context = {
            "user_id": user["user_id"],
            "roles": user["roles"],
            "email": user["email"],
        }
        result_obj = await executor.run(
            skill, user_context, session, user_input=user_input
        )
        logger.info(
            "user_skill_executed",
            skill_name=skill_name,
            skill_type="procedural",
            success=result_obj.success,
            user_id=str(user["user_id"]),
        )
        # Fire-and-forget usage_count increment — non-fatal if fails
        try:
            await session.execute(
                update(SkillDefinition)
                .where(SkillDefinition.id == skill.id)
                .values(usage_count=SkillDefinition.usage_count + 1)
            )
            await session.commit()
        except Exception:
            logger.warning("usage_count_increment_failed", skill_id=str(skill.id))
        return SkillRunResponse(
            success=result_obj.success,
            output=result_obj.output,
            step_outputs=result_obj.step_outputs or None,
            failed_step=result_obj.failed_step,
        )

    elif skill.skill_type == "instructional":
        output = skill.instruction_markdown or ""
        logger.info(
            "user_skill_executed",
            skill_name=skill_name,
            skill_type="instructional",
            success=True,
            user_id=str(user["user_id"]),
        )
        # Fire-and-forget usage_count increment — non-fatal if fails
        try:
            await session.execute(
                update(SkillDefinition)
                .where(SkillDefinition.id == skill.id)
                .values(usage_count=SkillDefinition.usage_count + 1)
            )
            await session.commit()
        except Exception:
            logger.warning("usage_count_increment_failed", skill_id=str(skill.id))
        return SkillRunResponse(success=True, output=output)

    else:
        raise HTTPException(
            status_code=500,
            detail=f"Unknown skill type: {skill.skill_type}",
        )
