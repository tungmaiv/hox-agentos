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
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.skill_definition import SkillDefinition
from core.models.user import UserContext
from core.schemas.registry import SkillListItem, SkillRunResponse
from security.deps import get_current_user
from security.rbac import batch_check_artifact_permissions, check_artifact_permission, has_permission
from skills.executor import SkillExecutor

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/skills", tags=["skills"])


class SkillRunRequest(BaseModel):
    """Optional user input for skill execution."""

    user_input: dict[str, Any] | None = None


async def _require_chat(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    """Gate 2 dependency: require 'chat' permission."""
    if not await has_permission(user, "chat", session):
        raise HTTPException(status_code=403, detail="Chat permission required")
    return user


@router.get("")
async def list_user_skills(
    user: UserContext = Depends(_require_chat),
    session: AsyncSession = Depends(get_db),
) -> list[SkillListItem]:
    """List skills available to the current user.

    Filters:
    1. Only active skills (status='active' AND is_active=True)
    2. Excludes skills denied by artifact_permissions for user's roles
    3. Respects user_artifact_permissions per-user overrides
    """
    result = await session.execute(
        select(SkillDefinition).where(
            SkillDefinition.status == "active",
            SkillDefinition.is_active == True,  # noqa: E712
        )
    )
    skills = result.scalars().all()

    # Batch permission check: 2 queries instead of N per-skill queries
    all_ids = [skill.id for skill in skills]
    allowed_ids = await batch_check_artifact_permissions(
        user, "skill", all_ids, session
    )
    visible = [
        SkillListItem.model_validate(skill)
        for skill in skills
        if skill.id in allowed_ids
    ]

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
    session: AsyncSession = Depends(get_db),
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
        return SkillRunResponse(success=True, output=output)

    else:
        raise HTTPException(
            status_code=500,
            detail=f"Unknown skill type: {skill.skill_type}",
        )
