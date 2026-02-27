"""
Channel integration API routes.

POST /api/channels/incoming  -- receives InternalMessage from sidecars (no auth)
POST /api/channels/pair      -- generate pairing code (requires JWT)
GET  /api/channels/accounts  -- list user's linked channel accounts (requires JWT)
DELETE /api/channels/accounts/{account_id} -- unlink a channel account (requires JWT)

Security notes:
  - /incoming is internal-only (Docker network isolation, no JWT)
  - /pair, /accounts require JWT via get_current_user dependency
"""
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from channels.gateway import ChannelGateway
from channels.models import InternalMessage
from core.db import get_db
from core.models.channel import ChannelAccount
from core.models.user import UserContext
from security.deps import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/channels", tags=["channels"])

# -- Gateway singleton -------------------------------------------------------

_gateway: ChannelGateway | None = None


def get_channel_gateway() -> ChannelGateway:
    """Return the singleton ChannelGateway. Initialized on first call."""
    global _gateway
    if _gateway is None:
        from core.config import settings

        sidecar_urls = {
            "telegram": getattr(settings, "telegram_gateway_url", "http://telegram-gateway:9001"),
            "whatsapp": getattr(settings, "whatsapp_gateway_url", "http://whatsapp-gateway:9002"),
            "ms_teams": getattr(settings, "teams_gateway_url", "http://teams-gateway:9003"),
        }
        _gateway = ChannelGateway(sidecar_urls=sidecar_urls)
    return _gateway


# -- Schemas -----------------------------------------------------------------


class PairRequest(BaseModel):
    channel: str


class PairResponse(BaseModel):
    code: str
    expires_in: int


class ChannelAccountResponse(BaseModel):
    id: UUID
    channel: str
    external_user_id: str
    display_name: str | None
    is_paired: bool


# -- Routes ------------------------------------------------------------------


@router.post("/incoming")
async def channel_incoming(
    msg: InternalMessage,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Receive an InternalMessage from a channel sidecar.

    No JWT auth -- this endpoint is internal-only (Docker network isolation).
    """
    gateway = get_channel_gateway()
    await gateway.handle_inbound(msg, db)
    return {"ok": True}


@router.post("/pair", response_model=PairResponse)
async def generate_pair_code(
    body: PairRequest,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PairResponse:
    """Generate a 6-digit pairing code for linking a channel account."""
    gateway = get_channel_gateway()
    code = await gateway.generate_pairing_code(user["user_id"], body.channel, db)
    return PairResponse(code=code, expires_in=600)


@router.get("/accounts", response_model=list[ChannelAccountResponse])
async def list_accounts(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChannelAccountResponse]:
    """List the authenticated user's linked channel accounts."""
    result = await db.execute(
        select(ChannelAccount).where(
            and_(
                ChannelAccount.user_id == user["user_id"],
                ChannelAccount.is_paired == True,  # noqa: E712
            )
        )
    )
    accounts = result.scalars().all()
    return [
        ChannelAccountResponse(
            id=a.id,
            channel=a.channel,
            external_user_id=a.external_user_id,
            display_name=a.display_name,
            is_paired=a.is_paired,
        )
        for a in accounts
    ]


@router.delete("/accounts/{account_id}", status_code=204)
async def unlink_account(
    account_id: UUID,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Unlink a channel account. Only the owning user can unlink."""
    result = await db.execute(
        select(ChannelAccount).where(
            and_(
                ChannelAccount.id == account_id,
                ChannelAccount.user_id == user["user_id"],
            )
        )
    )
    acct = result.scalar_one_or_none()
    if not acct:
        raise HTTPException(status_code=404, detail="Channel account not found")

    await db.delete(acct)
    await db.commit()
    logger.info(
        "channel_unlinked",
        user_id=str(user["user_id"]),
        channel=acct.channel,
    )
