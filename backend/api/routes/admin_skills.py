"""
Admin CRUD API for skill definitions — multi-version + bulk status + validate + import + review.

GET    /api/admin/skills                      — list all skill definitions (optional filters)
POST   /api/admin/skills                      — create a new skill definition
GET    /api/admin/skills/pending              — list skills pending review
POST   /api/admin/skills/import               — import skill from URL or inline content
GET    /api/admin/skills/{skill_id}           — get skill by UUID
PUT    /api/admin/skills/{skill_id}           — update skill fields
PATCH  /api/admin/skills/{skill_id}/status    — enable/disable with graceful removal
PATCH  /api/admin/skills/{skill_id}/activate  — activate version, deactivate others
PATCH  /api/admin/skills/bulk-status          — bulk status update
POST   /api/admin/skills/{skill_id}/validate  — dry-run validate skill procedure
POST   /api/admin/skills/{skill_id}/review    — approve or reject quarantined skill
GET    /api/admin/skills/{skill_id}/security-report — get security scan report

Security: requires `registry:manage` permission (Gate 2 RBAC).
"""
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.skill_definition import SkillDefinition
from core.models.user import UserContext
from core.schemas.registry import (
    BulkStatusUpdate,
    SecurityReportResponse,
    SkillDefinitionCreate,
    SkillDefinitionResponse,
    SkillDefinitionUpdate,
    SkillImportRequest,
    SkillReviewRequest,
    StatusUpdate,
)
from security.deps import get_current_user
from security.rbac import has_permission
from skills.importer import SkillImportError, SkillImporter
from skills.security_scanner import SecurityScanner
from skills.validator import SkillValidator

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/admin/skills", tags=["admin-skills"])


async def _require_registry_manager(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    """Gate 2 dependency: require registry:manage permission."""
    if not await has_permission(user, "registry:manage", session):
        raise HTTPException(status_code=403, detail="Registry manage permission required")
    return user


@router.get("")
async def list_skills(
    status: str | None = Query(None, description="Filter by status"),
    skill_type: str | None = Query(None, description="Filter by skill_type"),
    version: str | None = Query(None, description="Filter by version"),
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> list[SkillDefinitionResponse]:
    """List all skill definitions with optional filters."""
    stmt = select(SkillDefinition)
    if status is not None:
        stmt = stmt.where(SkillDefinition.status == status)
    if skill_type is not None:
        stmt = stmt.where(SkillDefinition.skill_type == skill_type)
    if version is not None:
        stmt = stmt.where(SkillDefinition.version == version)
    result = await session.execute(stmt)
    skills = result.scalars().all()
    logger.info("admin_skills_listed", user_id=str(user["user_id"]), count=len(skills))
    return [SkillDefinitionResponse.model_validate(s) for s in skills]


@router.post("", status_code=201)
async def create_skill(
    body: SkillDefinitionCreate,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> SkillDefinitionResponse:
    """Create a new skill definition."""
    skill = SkillDefinition(
        name=body.name,
        display_name=body.display_name,
        description=body.description,
        version=body.version,
        skill_type=body.skill_type,
        slash_command=body.slash_command,
        source_type=body.source_type,
        instruction_markdown=body.instruction_markdown,
        procedure_json=body.procedure_json,
        input_schema=body.input_schema,
        output_schema=body.output_schema,
        created_by=user["user_id"],
    )
    session.add(skill)
    await session.commit()
    await session.refresh(skill)
    logger.info(
        "admin_skill_created",
        skill_id=str(skill.id),
        name=skill.name,
        user_id=str(user["user_id"]),
    )
    return SkillDefinitionResponse.model_validate(skill)


@router.get("/pending")
async def list_pending_skills(
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> list[SkillDefinitionResponse]:
    """List skills with status='pending_review' for admin review queue."""
    result = await session.execute(
        select(SkillDefinition).where(SkillDefinition.status == "pending_review")
    )
    skills = result.scalars().all()
    logger.info(
        "admin_skills_pending_listed",
        user_id=str(user["user_id"]),
        count=len(skills),
    )
    return [SkillDefinitionResponse.model_validate(s) for s in skills]


@router.get("/check-name")
async def check_skill_name(
    name: str = Query(..., min_length=1),
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Returns {"available": true/false} for the given skill name (case-insensitive)."""
    count = await session.scalar(
        select(func.count()).where(
            func.lower(SkillDefinition.name) == name.lower(),
            SkillDefinition.is_active == True,  # noqa: E712
        )
    )
    return {"available": (count or 0) == 0}


@router.patch("/bulk-status")
async def bulk_status_update(
    body: BulkStatusUpdate,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Bulk update status for multiple skills."""
    result = await session.execute(
        update(SkillDefinition)
        .where(SkillDefinition.id.in_(body.ids))
        .values(status=body.status)
    )
    await session.commit()
    count = result.rowcount
    logger.info(
        "admin_skills_bulk_status",
        status=body.status,
        count=count,
        user_id=str(user["user_id"]),
    )
    return {"updated": count, "status": body.status}


@router.post("/import", status_code=201)
async def import_skill(
    body: SkillImportRequest,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Import a skill from URL or inline content.

    Flow: parse -> validate -> security scan -> quarantine (status=pending_review).
    """
    importer = SkillImporter()
    scanner = SecurityScanner()

    # Step 1: Parse
    try:
        if body.source_url:
            skill_data = await importer.import_from_url(body.source_url)
        elif body.content:
            skill_data = importer.parse_skill_md(body.content)
        else:
            raise HTTPException(
                status_code=400,
                detail="At least one of source_url or content required",
            )
    except SkillImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Step 2: Validate (if procedural)
    if skill_data.get("skill_type") == "procedural" and skill_data.get("procedure_json"):
        validator = SkillValidator()
        errors = validator.validate_procedure(skill_data["procedure_json"])
        if errors:
            raise HTTPException(
                status_code=400,
                detail={"message": "Skill validation failed", "errors": errors},
            )

    # Step 3: Security scan
    report = scanner.scan(skill_data, source_url=body.source_url)

    # Step 4: Create with pending_review status (quarantine)
    skill = SkillDefinition(
        name=skill_data["name"],
        display_name=skill_data.get("display_name"),
        description=skill_data.get("description"),
        version=skill_data.get("version", "1.0.0"),
        skill_type=skill_data.get("skill_type", "instructional"),
        slash_command=skill_data.get("slash_command"),
        source_type="imported",
        instruction_markdown=skill_data.get("instruction_markdown"),
        procedure_json=skill_data.get("procedure_json"),
        input_schema=skill_data.get("input_schema"),
        output_schema=skill_data.get("output_schema"),
        status="pending_review",
        is_active=False,
        security_score=report.score,
        security_report={
            "score": report.score,
            "factors": report.factors,
            "recommendation": report.recommendation,
            "injection_matches": report.injection_matches,
        },
        created_by=user["user_id"],
    )
    session.add(skill)
    await session.commit()
    await session.refresh(skill)

    logger.info(
        "admin_skill_imported",
        skill_id=str(skill.id),
        name=skill.name,
        security_score=report.score,
        recommendation=report.recommendation,
        user_id=str(user["user_id"]),
    )

    return {
        "skill": SkillDefinitionResponse.model_validate(skill).model_dump(mode="json"),
        "security_report": {
            "score": report.score,
            "factors": report.factors,
            "recommendation": report.recommendation,
            "injection_matches": report.injection_matches,
        },
    }


@router.get("/{skill_id}")
async def get_skill(
    skill_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> SkillDefinitionResponse:
    """Get a skill definition by UUID."""
    result = await session.execute(
        select(SkillDefinition).where(SkillDefinition.id == skill_id)
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return SkillDefinitionResponse.model_validate(skill)


@router.put("/{skill_id}")
async def update_skill(
    skill_id: UUID,
    body: SkillDefinitionUpdate,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> SkillDefinitionResponse:
    """Update a skill definition's fields."""
    result = await session.execute(
        select(SkillDefinition).where(SkillDefinition.id == skill_id)
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(skill, field, value)

    await session.commit()
    await session.refresh(skill)
    logger.info(
        "admin_skill_updated",
        skill_id=str(skill_id),
        user_id=str(user["user_id"]),
    )
    return SkillDefinitionResponse.model_validate(skill)


@router.patch("/{skill_id}/status")
async def patch_skill_status(
    skill_id: UUID,
    body: StatusUpdate,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Enable/disable a skill with graceful removal.

    When disabling/deprecating, returns count of active workflow runs
    referencing this skill so the admin can assess impact.
    """
    result = await session.execute(
        select(SkillDefinition).where(SkillDefinition.id == skill_id)
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    skill.status = body.status
    await session.commit()

    # Graceful removal: count active workflow runs referencing this skill
    active_workflow_runs = 0
    if body.status in ("disabled", "deprecated"):
        try:
            from core.models.workflow import WorkflowRun

            run_result = await session.execute(
                select(WorkflowRun).where(WorkflowRun.status == "running")
            )
            runs = run_result.scalars().all()
            for run in runs:
                if run.initial_state and skill.name in str(run.initial_state):
                    active_workflow_runs += 1
        except Exception:
            pass

    logger.info(
        "admin_skill_status_changed",
        skill_id=str(skill_id),
        status=body.status,
        active_workflow_runs=active_workflow_runs,
        user_id=str(user["user_id"]),
    )
    return {
        "updated": True,
        "status": body.status,
        "active_workflow_runs": active_workflow_runs,
    }


@router.patch("/{skill_id}/activate")
async def activate_skill_version(
    skill_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> SkillDefinitionResponse:
    """
    Activate a specific skill version — deactivates all other versions of the same name.

    Enables version rollback.
    """
    result = await session.execute(
        select(SkillDefinition).where(SkillDefinition.id == skill_id)
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    # Deactivate all versions of the same skill name
    await session.execute(
        update(SkillDefinition)
        .where(SkillDefinition.name == skill.name)
        .values(is_active=False)
    )

    # Activate this specific version
    skill.is_active = True
    await session.commit()
    await session.refresh(skill)

    logger.info(
        "admin_skill_version_activated",
        skill_id=str(skill_id),
        name=skill.name,
        version=skill.version,
        user_id=str(user["user_id"]),
    )
    return SkillDefinitionResponse.model_validate(skill)


@router.post("/{skill_id}/validate")
async def validate_skill(
    skill_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Dry-run validate a skill's procedure_json using SkillValidator."""
    result = await session.execute(
        select(SkillDefinition).where(SkillDefinition.id == skill_id)
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    errors: list[str] = []
    if skill.skill_type == "procedural" and skill.procedure_json:
        validator = SkillValidator()
        errors = validator.validate_procedure(skill.procedure_json)

    logger.info(
        "admin_skill_validated",
        skill_id=str(skill_id),
        errors=len(errors),
        user_id=str(user["user_id"]),
    )
    return {"skill_id": str(skill_id), "valid": len(errors) == 0, "errors": errors}


@router.post("/{skill_id}/review")
async def review_skill(
    skill_id: UUID,
    body: SkillReviewRequest,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Approve or reject a quarantined skill."""
    result = await session.execute(
        select(SkillDefinition).where(SkillDefinition.id == skill_id)
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    if skill.status != "pending_review":
        raise HTTPException(
            status_code=409,
            detail=f"Skill is not pending review (current status: {skill.status})",
        )

    now = datetime.now(timezone.utc)

    if body.decision == "approve":
        skill.status = "active"
        skill.is_active = True
        skill.reviewed_by = user["user_id"]
        skill.reviewed_at = now
    elif body.decision == "reject":
        skill.status = "rejected"
        skill.reviewed_by = user["user_id"]
        skill.reviewed_at = now
        # Store rejection notes in security_report
        if body.notes and skill.security_report:
            skill.security_report = {
                **skill.security_report,
                "rejection_notes": body.notes,
            }

    await session.commit()
    await session.refresh(skill)

    logger.info(
        "admin_skill_reviewed",
        skill_id=str(skill_id),
        decision=body.decision,
        user_id=str(user["user_id"]),
    )

    return {
        "skill_id": str(skill_id),
        "decision": body.decision,
        "status": skill.status,
    }


@router.get("/{skill_id}/security-report")
async def get_security_report(
    skill_id: UUID,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get stored security scan report for a skill."""
    result = await session.execute(
        select(SkillDefinition).where(SkillDefinition.id == skill_id)
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    if skill.security_report is None:
        raise HTTPException(
            status_code=404,
            detail="No security report available for this skill",
        )

    return skill.security_report
