"""
Auth configuration endpoint — public, no JWT required.

GET /api/auth/config → AuthConfigResponse

Tells the frontend whether SSO is available so the login page
can conditionally render the "Sign in with SSO" button.

sso_enabled  = admin has enabled SSO config in platform_config
sso_available = sso_enabled AND circuit breaker is NOT open
"""
from fastapi import APIRouter
from pydantic import BaseModel

from security.circuit_breaker import get_circuit_breaker
from security.keycloak_config import get_keycloak_config

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthConfigResponse(BaseModel):
    auth: str           # "local-only" or "local+keycloak"
    sso_enabled: bool = False
    sso_available: bool = False


@router.get("/config", response_model=AuthConfigResponse)
async def get_auth_config() -> AuthConfigResponse:
    """Return current authentication mode. No JWT required."""
    kc_config = await get_keycloak_config()
    if kc_config is not None and kc_config.enabled:
        cb = get_circuit_breaker()
        circuit_open = await cb.is_open()
        return AuthConfigResponse(
            auth="local+keycloak",
            sso_enabled=True,
            sso_available=not circuit_open,
        )
    return AuthConfigResponse(auth="local-only", sso_enabled=False, sso_available=False)
