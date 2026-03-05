"""
Local auth password change endpoint.

POST /api/auth/local/change-password — change password for a local auth user.

Requires JWT auth. The user must provide their current password to verify
identity before the new password is accepted. Enforces password complexity
requirements (min 8 chars, upper+lower+digit).

Security notes:
  - user_id always from JWT (never from request body)
  - Current password verified via bcrypt before updating
  - Passwords are never logged
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.local_auth import LocalUser
from core.models.user import UserContext
from security.deps import get_current_user, get_user_db
from security.local_auth import hash_password, verify_password

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/auth/local", tags=["local-auth"])


class ChangePasswordRequest(BaseModel):
    """Request body for password change."""

    current_password: str
    new_password: str


class ChangePasswordResponse(BaseModel):
    """Response for password change."""

    message: str


@router.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(
    body: ChangePasswordRequest,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_db),
) -> ChangePasswordResponse:
    """
    Change password for the current local auth user.

    Validates current password via bcrypt before accepting the new one.
    Enforces complexity requirements on the new password.

    Raises:
        HTTPException(400) — if the user is not a local auth user
        HTTPException(401) — if the current password is wrong
        HTTPException(422) — if the new password fails complexity requirements
    """
    result = await session.execute(
        select(LocalUser).where(LocalUser.id == user["user_id"])
    )
    local_user = result.scalar_one_or_none()

    if local_user is None:
        raise HTTPException(
            status_code=400,
            detail="Password change is only available for local auth users",
        )

    if not verify_password(body.current_password, local_user.password_hash):
        logger.info(
            "password_change_failed",
            user_id=str(user["user_id"]),
            reason="wrong_current_password",
        )
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    try:
        new_hash = hash_password(body.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    local_user.password_hash = new_hash
    await session.commit()

    logger.info("password_changed", user_id=str(user["user_id"]))
    return ChangePasswordResponse(message="Password updated successfully")
