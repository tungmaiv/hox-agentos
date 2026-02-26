"""
Admin configuration API — system-wide key/JSONB value store.

GET  /api/admin/config          — return all config entries as a dict
PUT  /api/admin/config/{key}    — upsert a single config entry

Security: admin-only via Gate 2 RBAC (tool:admin permission).
The "tool:admin" permission is granted only to the "it-admin" role (see security/rbac.py).
user_id for audit logging comes from JWT — never from the request body.
"""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.system_config import SystemConfig
from core.models.user import UserContext
from security.deps import get_current_user
from security.rbac import has_permission

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class ConfigUpdate(BaseModel):
    """Request body for updating a system config entry."""

    value: Any  # JSONB accepts any JSON-serializable value


async def _require_admin(user: UserContext = Depends(get_current_user)) -> UserContext:
    """
    Gate 2 dependency: deny non-admins with 403.

    Only users with the "it-admin" Keycloak role (which grants "tool:admin" permission)
    may access admin config endpoints.
    """
    if not has_permission(user, "tool:admin"):
        raise HTTPException(status_code=403, detail="Admin permission required")
    return user


@router.get("/config")
async def get_config(
    user: UserContext = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Return all system config entries as a {key: value} dict.

    Only available to admin users. Returns the JSONB values directly —
    booleans stay booleans, numbers stay numbers.
    """
    result = await session.execute(select(SystemConfig))
    rows = result.scalars().all()
    logger.info("config_read", user_id=str(user["user_id"]), count=len(rows))
    return {row.key: row.value for row in rows}


@router.put("/config/{key}")
async def update_config(
    key: str,
    body: ConfigUpdate,
    user: UserContext = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Upsert a single config entry by key.

    Creates the row if it does not exist; updates the value if it does.
    Returns the updated {key, value} pair.
    """
    result = await session.execute(
        select(SystemConfig).where(SystemConfig.key == key)
    )
    row = result.scalar_one_or_none()

    if row is None:
        row = SystemConfig(key=key, value=body.value)
        session.add(row)
    else:
        row.value = body.value

    await session.commit()
    logger.info("config_updated", key=key, user_id=str(user["user_id"]))
    return {"key": key, "value": body.value}
