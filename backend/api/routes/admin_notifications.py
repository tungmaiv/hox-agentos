"""
Admin Notifications API — Plan 26-01.

Generic notification CRUD for admin users. First consumer: SSO health.
Reusable by: skill activation (Phase 30), email system (Phase 33).

Endpoints:
  GET  /api/admin/notifications           — list notifications (optional ?unread_only=true)
  GET  /api/admin/notifications/count     — total + unread counts
  POST /api/admin/notifications/{id}/read — mark single as read
  POST /api/admin/notifications/read-all  — mark all as read
"""
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.admin_notification import AdminNotification
from core.models.user import UserContext
from security.deps import get_current_user
from security.rbac import has_permission

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["admin-notifications"])


# ---------------------------------------------------------------------------
# Security gate
# ---------------------------------------------------------------------------


async def _require_admin(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    if not await has_permission(user, "tool:admin", session):
        raise HTTPException(status_code=403, detail="Admin permission required")
    return user


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class NotificationResponse(BaseModel):
    id: str
    category: str
    severity: str
    title: str
    message: str
    is_read: bool
    created_at: str
    metadata_json: str | None = None


class NotificationCountResponse(BaseModel):
    total: int
    unread: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/api/admin/notifications")
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, le=100),
    user: UserContext = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List admin notifications, ordered by created_at DESC."""
    stmt = select(AdminNotification).order_by(AdminNotification.created_at.desc()).limit(limit)
    if unread_only:
        stmt = stmt.where(AdminNotification.is_read == False)  # noqa: E712

    result = await session.execute(stmt)
    notifications = result.scalars().all()

    return [
        {
            "id": str(n.id),
            "category": n.category,
            "severity": n.severity,
            "title": n.title,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "metadata_json": n.metadata_json,
        }
        for n in notifications
    ]


@router.get("/api/admin/notifications/count")
async def notification_count(
    user: UserContext = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> NotificationCountResponse:
    """Return total and unread notification counts."""
    total_result = await session.execute(
        select(func.count()).select_from(AdminNotification)
    )
    total = total_result.scalar() or 0

    unread_result = await session.execute(
        select(func.count())
        .select_from(AdminNotification)
        .where(AdminNotification.is_read == False)  # noqa: E712
    )
    unread = unread_result.scalar() or 0

    return NotificationCountResponse(total=total, unread=unread)


@router.post("/api/admin/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    user: UserContext = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Mark a single notification as read."""
    result = await session.execute(
        select(AdminNotification).where(AdminNotification.id == notification_id)
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    await session.commit()
    return {"status": "read"}


@router.post("/api/admin/notifications/read-all")
async def mark_all_read(
    user: UserContext = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Mark all notifications as read."""
    await session.execute(
        update(AdminNotification)
        .where(AdminNotification.is_read == False)  # noqa: E712
        .values(is_read=True)
    )
    await session.commit()
    return {"status": "all_read"}
