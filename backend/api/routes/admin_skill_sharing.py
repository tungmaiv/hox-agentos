"""
Admin skill sharing endpoints — grant/revoke/list user-level skill access.

POST   /api/admin/skills/{skill_id}/share              — grant user access to a skill
DELETE /api/admin/skills/{skill_id}/share/{user_id}    — revoke user access
GET    /api/admin/skills/{skill_id}/shares             — list all active shares for a skill

Security: requires `registry:manage` permission (Gate 2 RBAC — it-admin role).

Uses UserArtifactPermission with artifact_type='skill' to track per-user grants.
Returns 409 on duplicate share attempt (UNIQUE constraint on artifact_type + artifact_id + user_id).
"""
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.local_auth import LocalUser
from core.models.skill_definition import SkillDefinition
from core.models.user import UserContext
from core.models.user_artifact_permission import UserArtifactPermission
from core.schemas.registry import SkillShareEntry, SkillShareRequest
from security.deps import get_current_user
from security.rbac import has_permission

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/admin/skills", tags=["admin-skills-sharing"])


async def _require_registry_manager(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    """Gate 2 dependency: require registry:manage permission."""
    if not await has_permission(user, "registry:manage", session):
        raise HTTPException(
            status_code=403, detail="Registry manage permission required"
        )
    return user


@router.post("/{skill_id}/share", status_code=201)
async def share_skill_with_user(
    skill_id: UUID,
    body: SkillShareRequest,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> SkillShareEntry:
    """Grant a specific user access to a skill.

    Creates a UserArtifactPermission row with artifact_type='skill' and allowed=True.
    Returns 404 if the skill does not exist.
    Returns 409 if the user already has a share entry for this skill.
    """
    # Verify the skill exists
    skill_result = await session.execute(
        select(SkillDefinition).where(SkillDefinition.id == skill_id)
    )
    skill = skill_result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    permission = UserArtifactPermission(
        artifact_type="skill",
        artifact_id=skill_id,
        user_id=body.user_id,
        allowed=True,
        status="active",
    )
    session.add(permission)
    try:
        await session.commit()
        await session.refresh(permission)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"User {body.user_id} already has access to this skill",
        )

    logger.info(
        "admin_skill_shared",
        skill_id=str(skill_id),
        target_user_id=str(body.user_id),
        admin_user_id=str(user["user_id"]),
    )
    local_user_result = await session.execute(select(LocalUser).where(LocalUser.id == body.user_id))
    local_user = local_user_result.scalar_one_or_none()
    entry = SkillShareEntry(
        user_id=permission.user_id,
        created_at=permission.created_at,
        username=local_user.username if local_user else "",
        email=local_user.email if local_user else "",
    )
    return entry


@router.delete("/{skill_id}/share/{target_user_id}", status_code=204)
async def revoke_skill_share(
    skill_id: UUID,
    target_user_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Revoke a user's access to a skill.

    Deletes the UserArtifactPermission row.
    Returns 404 if no matching permission row exists.
    """
    result = await session.execute(
        select(UserArtifactPermission).where(
            UserArtifactPermission.artifact_type == "skill",
            UserArtifactPermission.artifact_id == skill_id,
            UserArtifactPermission.user_id == target_user_id,
        )
    )
    permission = result.scalar_one_or_none()
    if permission is None:
        raise HTTPException(
            status_code=404, detail="Share not found for this skill and user"
        )

    await session.delete(permission)
    await session.commit()

    logger.info(
        "admin_skill_share_revoked",
        skill_id=str(skill_id),
        target_user_id=str(target_user_id),
        admin_user_id=str(user["user_id"]),
    )


@router.get("/{skill_id}/shares")
async def list_skill_shares(
    skill_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> list[SkillShareEntry]:
    """List all active user shares for a skill.

    Returns a list of SkillShareEntry objects (user_id + created_at).
    """
    result = await session.execute(
        select(UserArtifactPermission).where(
            UserArtifactPermission.artifact_type == "skill",
            UserArtifactPermission.artifact_id == skill_id,
            UserArtifactPermission.status == "active",
        )
    )
    permissions = result.scalars().all()

    user_ids = [p.user_id for p in permissions]
    users_map: dict[object, LocalUser] = {}
    if user_ids:
        users_result = await session.execute(select(LocalUser).where(LocalUser.id.in_(user_ids)))
        users_map = {u.id: u for u in users_result.scalars().all()}

    logger.info(
        "admin_skill_shares_listed",
        skill_id=str(skill_id),
        count=len(permissions),
        admin_user_id=str(user["user_id"]),
    )
    return [
        SkillShareEntry(
            user_id=p.user_id,
            created_at=p.created_at,
            username=users_map[p.user_id].username if p.user_id in users_map else "",
            email=users_map[p.user_id].email if p.user_id in users_map else "",
        )
        for p in permissions
    ]
