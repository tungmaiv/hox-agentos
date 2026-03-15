"""
Admin SSO Health API — Plan 26-01.

Endpoints:
  GET  /api/admin/sso/health                     — categorized SSO health diagnostics
  PUT  /api/admin/sso/circuit-breaker/config      — update circuit breaker thresholds
  POST /api/admin/sso/circuit-breaker/reset       — manually reset circuit breaker to CLOSED
"""
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from core.models.platform_config import PlatformConfig
from core.models.user import UserContext
from security.circuit_breaker import get_circuit_breaker
from security.deps import get_current_user
from security.rbac import has_permission
from security.sso_health import SSOHealthStatus, check_sso_health

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["admin-sso-health"])


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


class CircuitBreakerConfigInput(BaseModel):
    failure_threshold: int
    recovery_timeout_seconds: int
    half_open_max_calls: int


class CircuitBreakerConfigResponse(BaseModel):
    failure_threshold: int
    recovery_timeout_seconds: int
    half_open_max_calls: int
    current_state: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/api/admin/sso/health")
async def get_sso_health(
    user: UserContext = Depends(_require_admin),
) -> dict[str, Any]:
    """Return categorized SSO health diagnostics with circuit breaker state."""
    status = await check_sso_health()
    return status.model_dump(mode="json")


@router.put("/api/admin/sso/circuit-breaker/config")
async def update_circuit_breaker_config(
    body: CircuitBreakerConfigInput,
    user: UserContext = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> CircuitBreakerConfigResponse:
    """Update circuit breaker thresholds. Persists to platform_config and updates in-memory state."""
    cb = get_circuit_breaker()
    cb.update_thresholds(
        failure_threshold=body.failure_threshold,
        recovery_timeout_seconds=float(body.recovery_timeout_seconds),
        half_open_max_calls=body.half_open_max_calls,
    )

    # Persist to DB
    result = await session.execute(
        select(PlatformConfig).where(PlatformConfig.id == 1)
    )
    row = result.scalar_one_or_none()
    if row:
        row.cb_failure_threshold = body.failure_threshold
        row.cb_recovery_timeout = body.recovery_timeout_seconds
        row.cb_half_open_max_calls = body.half_open_max_calls
        await session.commit()

    logger.info(
        "circuit_breaker_config_updated",
        admin_user=str(user["user_id"]),
        failure_threshold=body.failure_threshold,
        recovery_timeout=body.recovery_timeout_seconds,
    )

    return CircuitBreakerConfigResponse(
        failure_threshold=cb.failure_threshold,
        recovery_timeout_seconds=int(cb.recovery_timeout_seconds),
        half_open_max_calls=cb.half_open_max_calls,
        current_state=cb.state.value,
    )


@router.post("/api/admin/sso/circuit-breaker/reset")
async def reset_circuit_breaker(
    user: UserContext = Depends(_require_admin),
) -> dict[str, str]:
    """Manually reset circuit breaker to CLOSED state (admin override)."""
    cb = get_circuit_breaker()
    cb.reset()
    logger.info("circuit_breaker_admin_reset", admin_user=str(user["user_id"]))
    return {"status": "reset", "state": cb.state.value}
