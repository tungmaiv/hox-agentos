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
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import asc, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.user import UserContext
from core.models.user_artifact_permission import UserArtifactPermission
from core.schemas.registry import SkillListItem, SkillRunResponse
from registry.models import RegistryEntry
from security.deps import get_current_user, get_user_db
from security.rbac import batch_check_artifact_permissions, check_artifact_permission, has_permission
from skill_export.exporter import build_skill_zip
from skills.executor import SkillExecutor

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/skills", tags=["skills"])


class _SkillAdapter:
    """Duck-type adapter that exposes RegistryEntry config keys as attributes.

    SkillExecutor and build_skill_zip use getattr() on a skill object, so this
    class makes a RegistryEntry behave like a SkillDefinition for those callers.
    """

    def __init__(self, entry: RegistryEntry) -> None:
        self._entry = entry
        self._cfg: dict[str, Any] = entry.config or {}

    # RegistryEntry columns exposed directly
    @property
    def id(self) -> Any:
        return self._entry.id

    @property
    def name(self) -> str:
        return self._entry.name

    @property
    def display_name(self) -> str | None:
        return self._entry.display_name

    @property
    def description(self) -> str | None:
        return self._entry.description

    # Config-derived attributes
    @property
    def skill_type(self) -> str:
        return self._cfg.get("skill_type", "instructional")

    @property
    def version(self) -> str:
        return self._cfg.get("version", "1.0.0")

    @property
    def slash_command(self) -> str | None:
        return self._cfg.get("slash_command")

    @property
    def instruction_markdown(self) -> str | None:
        return self._cfg.get("instruction_markdown")

    @property
    def procedure_json(self) -> dict[str, Any] | None:
        return self._cfg.get("procedure_json")

    @property
    def input_schema(self) -> dict[str, Any] | None:
        return self._cfg.get("input_schema")

    @property
    def output_schema(self) -> dict[str, Any] | None:
        return self._cfg.get("output_schema")

    @property
    def allowed_tools(self) -> list[str] | None:
        return self._cfg.get("allowed_tools")

    @property
    def tags(self) -> list[str] | None:
        return self._cfg.get("tags")

    @property
    def category(self) -> str | None:
        return self._cfg.get("category")

    @property
    def license(self) -> str | None:
        return self._cfg.get("license")

    @property
    def compatibility(self) -> str | None:
        return self._cfg.get("compatibility")

    @property
    def metadata_json(self) -> dict[str, Any] | None:
        return self._cfg.get("metadata_json")

    @property
    def source_type(self) -> str:
        return self._cfg.get("source_type", "user_created")

    @property
    def source_url(self) -> str | None:
        return self._cfg.get("source_url")

    @property
    def security_score(self) -> int | None:
        return self._cfg.get("security_score")

    @property
    def is_promoted(self) -> bool:
        return bool(self._cfg.get("is_promoted", False))

    @property
    def usage_count(self) -> int:
        return int(self._cfg.get("usage_count", 0))


def _entry_to_skill_list_item(entry: RegistryEntry, is_shared: bool = False) -> SkillListItem:
    """Build a SkillListItem from a RegistryEntry."""
    cfg: dict[str, Any] = entry.config or {}
    return SkillListItem(
        id=entry.id,
        name=entry.name,
        display_name=entry.display_name,
        description=entry.description,
        slash_command=cfg.get("slash_command"),
        usage_count=int(cfg.get("usage_count", 0)),
        is_promoted=bool(cfg.get("is_promoted", False)),
        is_shared=is_shared,
    )


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
    promoted: bool | None = Query(None, description="Filter to promoted skills only"),
    user: UserContext = Depends(_require_chat),
    session: AsyncSession = Depends(get_user_db),
) -> list[SkillListItem]:
    """List skills available to the current user.

    Returns all active skills with is_shared field from UserArtifactPermission JOIN.
    ACL enforcement is only applied at run time (POST /api/skills/{name}/run).
    Supports full-text search, category, skill_type, promoted, and sort filtering.
    """
    # Correlated EXISTS subquery to check if current user has a shared permission
    shared_subq = (
        select(UserArtifactPermission.id)
        .where(
            UserArtifactPermission.artifact_type == "skill",
            UserArtifactPermission.artifact_id == RegistryEntry.id,
            UserArtifactPermission.user_id == user["user_id"],
            UserArtifactPermission.allowed == True,  # noqa: E712
            UserArtifactPermission.status == "active",
        )
        .exists()
        .label("is_shared")
    )

    stmt = select(RegistryEntry, shared_subq).where(
        RegistryEntry.type == "skill",
        RegistryEntry.status == "active",
    )
    if q:
        stmt = stmt.where(
            or_(
                RegistryEntry.name.ilike(f"%{q}%"),
                RegistryEntry.description.ilike(f"%{q}%"),
            )
        )
    if category is not None:
        stmt = stmt.where(RegistryEntry.config["category"].as_string() == category)
    if skill_type is not None:
        stmt = stmt.where(RegistryEntry.config["skill_type"].as_string() == skill_type)
    if promoted is not None:
        # JSON boolean cast: compare as string "true"/"false"
        if promoted:
            stmt = stmt.where(RegistryEntry.config["is_promoted"].as_string() == "true")
        else:
            stmt = stmt.where(
                or_(
                    RegistryEntry.config["is_promoted"].as_string() == "false",
                    RegistryEntry.config["is_promoted"].is_(None),
                )
            )
    if sort == "oldest":
        stmt = stmt.order_by(asc(RegistryEntry.created_at))
    else:
        stmt = stmt.order_by(desc(RegistryEntry.created_at))  # newest default; most_used not supported

    result = await session.execute(stmt)
    rows = result.all()
    items: list[SkillListItem] = []
    for entry, is_shared in rows:
        item = _entry_to_skill_list_item(entry, is_shared=bool(is_shared))
        items.append(item)

    logger.info(
        "user_skills_listed",
        user_id=str(user["user_id"]),
        total=len(items),
    )
    return items


@router.get("/{skill_id}/export")
async def export_user_skill(
    skill_id: UUID,
    user: UserContext = Depends(_require_chat),
    session: AsyncSession = Depends(get_user_db),
) -> StreamingResponse:
    """Download a skill as an agentskills.io-compliant ZIP archive.

    Any authenticated user with 'chat' permission can export any active skill.
    Returns 404 for unknown or inactive skills.
    """
    result = await session.execute(
        select(RegistryEntry).where(
            RegistryEntry.id == skill_id,
            RegistryEntry.type == "skill",
            RegistryEntry.status == "active",
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Skill not found or not active")
    adapter = _SkillAdapter(entry)
    zip_bytes = build_skill_zip(adapter)  # type: ignore[arg-type]
    filename = f"{adapter.name}-{adapter.version}.zip"
    logger.info(
        "user_skill_exported",
        skill_id=str(skill_id),
        skill_name=adapter.name,
        user_id=str(user["user_id"]),
    )
    return StreamingResponse(
        zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{skill_name}/run")
async def run_user_skill(
    skill_name: str,
    body: SkillRunRequest | None = None,
    user: UserContext = Depends(_require_chat),
    session: AsyncSession = Depends(get_user_db),
) -> SkillRunResponse:
    """Execute a skill by name.

    - Lookup skill by name WHERE type='skill' AND status='active'. If not found -> 404.
    - Check artifact permission for user's roles. If denied -> 403.
    - Dispatch based on skill_type:
      - procedural: SkillExecutor.run() with tool call pipeline
      - instructional: Return instruction_markdown content
    """
    result = await session.execute(
        select(RegistryEntry).where(
            RegistryEntry.name == skill_name,
            RegistryEntry.type == "skill",
            RegistryEntry.status == "active",
        )
    )
    entry = result.scalar_one_or_none()

    if entry is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found or not active")

    # Check artifact permission
    allowed = await check_artifact_permission(user, "skill", entry.id, session)
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: not authorized for skill '{skill_name}'",
        )

    adapter = _SkillAdapter(entry)
    user_input = body.user_input if body else None

    if adapter.skill_type == "procedural":
        executor = SkillExecutor()
        user_context = {
            "user_id": user["user_id"],
            "roles": user["roles"],
            "email": user["email"],
        }
        result_obj = await executor.run(
            adapter, user_context, session, user_input=user_input  # type: ignore[arg-type]
        )
        logger.info(
            "user_skill_executed",
            skill_name=skill_name,
            skill_type="procedural",
            success=result_obj.success,
            user_id=str(user["user_id"]),
        )
        # Fire-and-forget usage_count increment stored in config JSONB — non-fatal if fails
        try:
            new_count = int((entry.config or {}).get("usage_count", 0)) + 1
            entry.config = {**(entry.config or {}), "usage_count": new_count}
            session.add(entry)
            await session.commit()
        except Exception:
            logger.warning("usage_count_increment_failed", skill_id=str(entry.id))
        return SkillRunResponse(
            success=result_obj.success,
            output=result_obj.output,
            step_outputs=result_obj.step_outputs or None,
            failed_step=result_obj.failed_step,
        )

    elif adapter.skill_type == "instructional":
        output = adapter.instruction_markdown or ""
        logger.info(
            "user_skill_executed",
            skill_name=skill_name,
            skill_type="instructional",
            success=True,
            user_id=str(user["user_id"]),
        )
        # Fire-and-forget usage_count increment stored in config JSONB — non-fatal if fails
        try:
            new_count = int((entry.config or {}).get("usage_count", 0)) + 1
            entry.config = {**(entry.config or {}), "usage_count": new_count}
            session.add(entry)
            await session.commit()
        except Exception:
            logger.warning("usage_count_increment_failed", skill_id=str(entry.id))
        return SkillRunResponse(success=True, output=output)

    else:
        raise HTTPException(
            status_code=500,
            detail=f"Unknown skill type: {adapter.skill_type}",
        )
