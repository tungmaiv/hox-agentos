"""
Auth configuration endpoint — public, no JWT required.

GET /api/auth/config → AuthConfigResponse

Tells the frontend whether SSO is available so the login page
can conditionally render the "Sign in with SSO" button.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from security.keycloak_config import get_keycloak_config

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthConfigResponse(BaseModel):
    auth: str           # "local-only" or "local+keycloak"
    sso_enabled: bool = False


@router.get("/config", response_model=AuthConfigResponse)
async def get_auth_config() -> AuthConfigResponse:
    """Return current authentication mode. No JWT required."""
    kc_config = await get_keycloak_config()
    if kc_config is not None and kc_config.enabled:
        return AuthConfigResponse(auth="local+keycloak", sso_enabled=True)
    return AuthConfigResponse(auth="local-only", sso_enabled=False)
