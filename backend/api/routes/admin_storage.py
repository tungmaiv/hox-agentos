"""
Admin Storage Settings API — Plan 28-04.

Manages storage configuration (max file size, allowed MIME types) via system_config table.
All endpoints require it-admin role (tool:admin permission).

Endpoints:
  GET /api/admin/storage/settings — read storage config (returns defaults if not set)
  PUT /api/admin/storage/settings — upsert storage config keys
"""
from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.system_config import SystemConfig
from core.models.user import UserContext
from security.deps import get_current_user
from security.rbac import has_permission

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/admin/storage", tags=["admin-storage"])

# Default values for storage settings
DEFAULT_MAX_FILE_SIZE_MB = 100
DEFAULT_ALLOWED_MIME_TYPES = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/csv",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
]

STORAGE_KEY_MAX_SIZE = "storage.max_file_size_mb"
STORAGE_KEY_MIME_TYPES = "storage.allowed_mime_types"


# ---------------------------------------------------------------------------
# Security gate
# ---------------------------------------------------------------------------


async def _require_admin(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    """Gate 2 dependency: require tool:admin permission (it-admin role only)."""
    if not await has_permission(user, "tool:admin", session):
        raise HTTPException(status_code=403, detail="Admin permission required")
    return user


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class StorageSettingsResponse(BaseModel):
    max_file_size_mb: int
    allowed_mime_types: list[str]


class StorageSettingsUpdate(BaseModel):
    max_file_size_mb: int = Field(..., ge=1, le=500)
    allowed_mime_types: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/settings")
async def get_storage_settings(
    user: UserContext = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> StorageSettingsResponse:
    """Read storage settings from system_config. Returns defaults if keys not present."""
    # Read max file size
    max_size_result = await session.execute(
        select(SystemConfig).where(SystemConfig.key == STORAGE_KEY_MAX_SIZE)
    )
    max_size_row = max_size_result.scalar_one_or_none()
    max_file_size_mb = (
        int(max_size_row.value) if max_size_row is not None else DEFAULT_MAX_FILE_SIZE_MB
    )

    # Read allowed MIME types
    mime_result = await session.execute(
        select(SystemConfig).where(SystemConfig.key == STORAGE_KEY_MIME_TYPES)
    )
    mime_row = mime_result.scalar_one_or_none()
    allowed_mime_types: list[str] = (
        list(mime_row.value) if mime_row is not None else DEFAULT_ALLOWED_MIME_TYPES
    )

    logger.info(
        "admin_storage_settings_read",
        user_id=str(user["user_id"]),
        max_file_size_mb=max_file_size_mb,
    )
    return StorageSettingsResponse(
        max_file_size_mb=max_file_size_mb,
        allowed_mime_types=allowed_mime_types,
    )


@router.put("/settings")
async def update_storage_settings(
    body: StorageSettingsUpdate,
    user: UserContext = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> StorageSettingsResponse:
    """Upsert storage settings in system_config. Returns updated settings."""
    # Upsert max file size
    max_size_result = await session.execute(
        select(SystemConfig).where(SystemConfig.key == STORAGE_KEY_MAX_SIZE)
    )
    max_size_row = max_size_result.scalar_one_or_none()
    if max_size_row is not None:
        max_size_row.value = body.max_file_size_mb
    else:
        max_size_row = SystemConfig(
            key=STORAGE_KEY_MAX_SIZE,
            value=body.max_file_size_mb,
        )
        session.add(max_size_row)

    # Upsert allowed MIME types
    mime_result = await session.execute(
        select(SystemConfig).where(SystemConfig.key == STORAGE_KEY_MIME_TYPES)
    )
    mime_row = mime_result.scalar_one_or_none()
    if mime_row is not None:
        mime_row.value = body.allowed_mime_types
    else:
        mime_row = SystemConfig(
            key=STORAGE_KEY_MIME_TYPES,
            value=body.allowed_mime_types,
        )
        session.add(mime_row)

    await session.commit()

    logger.info(
        "admin_storage_settings_updated",
        user_id=str(user["user_id"]),
        max_file_size_mb=body.max_file_size_mb,
        mime_type_count=len(body.allowed_mime_types),
    )
    return StorageSettingsResponse(
        max_file_size_mb=body.max_file_size_mb,
        allowed_mime_types=body.allowed_mime_types,
    )
