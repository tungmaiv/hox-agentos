"""
Keycloak Admin API client for fetching user realm roles.

Used by Celery workflow workers to resolve the owner's current roles
before executing a workflow graph. This ensures tool ACL checks use
live role assignments rather than stale owner_roles_json snapshots.

Security: Uses client_credentials grant with the backend's service account.
The service account (blitz-backend) must have the realm-management >
view-users role assigned in Keycloak.

Error handling: All httpx errors propagate to the caller. Per locked decision:
"if Keycloak is unreachable, fail the workflow run".
"""
import httpx
import structlog

from core.config import get_settings

logger = structlog.get_logger(__name__)


async def fetch_user_realm_roles(user_id: str) -> list[str]:
    """
    Fetch a user's realm-level role names from the Keycloak Admin API.

    Uses the backend service account's client_credentials grant to obtain
    an admin token, then queries the user's realm role mappings.

    Args:
        user_id: The Keycloak user UUID string.

    Returns:
        List of realm role name strings (e.g. ["employee", "it-admin"]).

    Raises:
        httpx.HTTPError: If Keycloak is unreachable or returns an error.
        httpx.HTTPStatusError: If token or role endpoint returns non-2xx.
    """
    settings = get_settings()
    base = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"
    token_url = f"{base}/protocol/openid-connect/token"

    verify: str | bool = settings.keycloak_ca_cert or True

    async with httpx.AsyncClient(verify=verify, timeout=10.0) as client:
        # Step 1: Obtain admin access token via client credentials grant
        token_resp = await client.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.keycloak_client_id,
                "client_secret": settings.keycloak_client_secret,
            },
        )
        token_resp.raise_for_status()
        admin_token: str = token_resp.json()["access_token"]

        # Step 2: Fetch realm role mappings for the user
        roles_url = (
            f"{settings.keycloak_url}/admin/realms/{settings.keycloak_realm}"
            f"/users/{user_id}/role-mappings/realm"
        )
        roles_resp = await client.get(
            roles_url,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        roles_resp.raise_for_status()

        roles: list[str] = [r["name"] for r in roles_resp.json()]
        logger.info("keycloak_roles_fetched", user_id=user_id, roles=roles)
        return roles
