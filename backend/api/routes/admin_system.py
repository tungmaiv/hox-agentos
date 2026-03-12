"""
Admin system management routes.

POST /api/admin/system/rescan-skills — trigger batch retroactive security scan of all active skills.

Security: requires tool:admin permission (Gate 2 RBAC).
Scan runs asynchronously as a FastAPI BackgroundTask (no Celery needed for MVP).
"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.user import UserContext
from security.deps import get_current_user
from security.rbac import has_permission

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/admin/system", tags=["admin-system"])


async def _require_admin(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    """Gate 2 dependency: require tool:admin permission (it-admin role only)."""
    if not await has_permission(user, "tool:admin", session):
        raise HTTPException(status_code=403, detail="Admin permission required")
    return user


async def _run_batch_scan(user_id: str) -> None:
    """Background task: scan all active skills and update their security scores."""
    from sqlalchemy import select

    from core.db import async_session
    from registry.models import RegistryEntry
    from security.scan_client import SecurityScanClient, scan_skill_with_fallback

    scan_client = SecurityScanClient()
    async with async_session() as scan_session:
        result = await scan_session.execute(
            select(RegistryEntry).where(
                RegistryEntry.type == "skill",
                RegistryEntry.status == "active",
                RegistryEntry.deleted_at.is_(None),
            )
        )
        entries = result.scalars().all()
        logger.info(
            "rescan_skills_start",
            count=len(entries),
            user_id=user_id,
        )
        for entry in entries:
            try:
                config = entry.config or {}
                skill_data = {
                    "name": entry.name,
                    "scripts": config.get("instruction_markdown", ""),
                    "instruction_markdown": config.get("instruction_markdown", ""),
                    "requirements": config.get("requirements", ""),
                }
                scan_result = await scan_skill_with_fallback(skill_data, scan_client)
                updated_config = {
                    **config,
                    "security_score": scan_result.get("score"),
                    "security_report": scan_result,
                }
                entry.config = updated_config
                entry.updated_at = datetime.now(timezone.utc)
                scan_session.add(entry)
            except Exception as exc:
                logger.warning(
                    "rescan_skill_failed",
                    skill_id=str(entry.id),
                    skill_name=entry.name,
                    error=str(exc),
                )
        await scan_session.commit()
        logger.info("rescan_skills_complete", count=len(entries))


@router.get("/health")
async def get_system_health(
    user: UserContext = Depends(_require_admin),
) -> dict:
    """Return system health including security scanner availability. Admin only."""
    from security.scan_client import SecurityScanClient

    from core.config import settings

    scan_client = SecurityScanClient(base_url=settings.security_scanner_url)
    scanner_available = await scan_client.health_check()
    return {
        "status": "ok",
        "security_scanner_available": scanner_available,
    }


@router.post("/rescan-skills", status_code=202)
async def trigger_rescan_skills(
    background_tasks: BackgroundTasks,
    user: UserContext = Depends(_require_admin),
) -> dict:
    """Trigger batch re-scan of all active skills. Admin only.

    Runs as a FastAPI background task. Admin can monitor progress in server logs.
    Returns 202 Accepted immediately; scan runs asynchronously.
    """
    background_tasks.add_task(_run_batch_scan, str(user["user_id"]))
    logger.info("rescan_skills_triggered", user_id=str(user["user_id"]))
    return {
        "status": "accepted",
        "message": "Batch re-scan started as background task. Monitor server logs for progress.",
    }
