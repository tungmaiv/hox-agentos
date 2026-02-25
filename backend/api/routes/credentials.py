# backend/api/routes/credentials.py
"""
Credential management API — Phase 2 stubs.

GET  /api/credentials        — list connected providers for current user
DELETE /api/credentials/{provider} — disconnect a provider

POST is NOT implemented in Phase 2. OAuth callback handlers that create credentials
are added in Phase 3 when sub-agents need to call Google/Microsoft APIs.

Security: all queries use user_id from JWT — never from request body.
Credentials (token values) are NEVER returned in API responses.
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
from security.credentials import delete_credential
from security.deps import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/credentials", tags=["credentials"])


class ConnectedProvider(BaseModel):
    """A connected OAuth provider — token value is NEVER included in response."""

    provider: str
    connected_at: str  # ISO timestamp


@router.get("/", response_model=list[ConnectedProvider])
async def list_connected_providers(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[ConnectedProvider]:
    """
    List OAuth providers the current user has connected.

    Returns only provider names and timestamps — never token values.
    Isolation: WHERE user_id=$1 from JWT.
    """
    result = await session.execute(
        select(UserCredential)
        .where(UserCredential.user_id == user["user_id"])
        .order_by(UserCredential.created_at.desc())
    )
    rows = result.scalars().all()

    return [
        ConnectedProvider(
            provider=row.provider,
            connected_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


@router.delete("/{provider}", status_code=204)
async def disconnect_provider(
    provider: str,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """
    Disconnect (delete) a specific OAuth provider for the current user.

    Returns 204 No Content on success.
    Returns 404 if provider not found for this user.
    Isolation: delete_credential() enforces WHERE user_id=$1 — only deletes caller's credential.
    """
    deleted = await delete_credential(session, user_id=user["user_id"], provider=provider)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Provider '{provider}' not connected for this user",
        )
    logger.info(
        "provider_disconnected",
        user_id=str(user["user_id"]),
        provider=provider,
    )
