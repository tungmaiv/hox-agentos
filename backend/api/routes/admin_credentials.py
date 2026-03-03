"""
Admin credential management API.

GET    /api/admin/credentials                        — list all users' OAuth connections
DELETE /api/admin/credentials/{user_id}/{provider}   — admin force-revoke a credential

Security: requires registry:manage permission (Gate 2 RBAC).
Credentials (token values) are NEVER returned — only metadata.
"""
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.credentials import UserCredential
from core.models.user import UserContext
from security.deps import get_current_user
from security.rbac import has_permission

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/admin/credentials", tags=["admin-credentials"])


async def _require_registry_manager(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserContext:
    """Gate 2 dependency: require registry:manage permission."""
    if not await has_permission(user, "registry:manage", session):
        raise HTTPException(status_code=403, detail="Registry manage permission required")
    return user


class AdminCredentialView(BaseModel):
    """OAuth credential metadata view — token values are NEVER included."""

    user_id: str          # UUID as string (no FK to user table — users live in Keycloak)
    provider: str
    connected_at: str     # ISO timestamp — never token values


@router.get("", response_model=list[AdminCredentialView])
async def list_all_credentials(
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> list[AdminCredentialView]:
    """List all users' OAuth connections. Never returns token values."""
    async with session.begin():
        result = await session.execute(
            select(UserCredential).order_by(UserCredential.user_id, UserCredential.provider)
        )
        rows = result.scalars().all()
    logger.info("admin_credentials_listed", user_id=str(user["user_id"]), count=len(rows))
    return [
        AdminCredentialView(
            user_id=str(row.user_id),
            provider=row.provider,
            connected_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


@router.delete("/{user_id}/{provider}", status_code=204)
async def admin_revoke_credential(
    user_id: UUID,
    provider: str,
    user: UserContext = Depends(_require_registry_manager),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Admin force-revoke a credential for any user. Returns 404 if not found."""
    async with session.begin():
        result = await session.execute(
            select(UserCredential).where(
                UserCredential.user_id == user_id,
                UserCredential.provider == provider,
            )
        )
        cred = result.scalar_one_or_none()
        if cred is None:
            raise HTTPException(status_code=404, detail="Credential not found")
        await session.delete(cred)
    logger.info(
        "admin_credential_revoked",
        target_user_id=str(user_id),
        provider=provider,
        admin_user_id=str(user["user_id"]),
    )
