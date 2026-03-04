"""
Export route for skill definitions.

GET /api/admin/skills/{skill_id}/export — returns a downloadable zip file.

This router uses the same prefix as admin_skills so the export route
can be included alongside the existing CRUD routes. The export route
must be declared BEFORE /{skill_id} UUID routes to prevent routing
collision in FastAPI (literal path segments take precedence when declared
first — this is handled by the order of router inclusion in admin_skills.py).

Security: requires registry:manage permission (Gate 2 RBAC), same as all
other admin skill endpoints.
"""
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.skill_definition import SkillDefinition
from core.models.user import UserContext
from security.deps import get_current_user
from security.rbac import has_permission
from skill_export.exporter import build_skill_zip

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/admin/skills", tags=["admin-skills-export"])


async def _require_registry_manager(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    """Gate 2 dependency: require registry:manage permission."""
    if not await has_permission(user, "registry:manage", session):
        raise HTTPException(status_code=403, detail="Registry manage permission required")
    return user


@router.get("/{skill_id}/export")
async def export_skill(
    skill_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Export a skill definition as an agentskills.io-compliant zip file.

    Returns a zip archive containing:
      - SKILL.md with YAML frontmatter and instructions
      - scripts/procedure.json (procedural skills only)
      - references/schemas.json (when input/output schemas are defined)

    The file is named {skill.name}-{skill.version}.zip.
    Works for skills in any status (active, pending_review, disabled).
    """
    from sqlalchemy import select

    result = await session.execute(
        select(SkillDefinition).where(SkillDefinition.id == skill_id)
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    zip_bytes = build_skill_zip(skill)
    filename = f"{skill.name}-{skill.version}.zip"

    logger.info(
        "admin_skill_exported",
        skill_id=str(skill_id),
        skill_name=skill.name,
        filename=filename,
        user_id=str(user["user_id"]),
    )

    return StreamingResponse(
        zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
