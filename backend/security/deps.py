"""
FastAPI dependencies for authentication and authorization.

get_current_user() is the single entry point for Gate 1 (JWT validation).
All protected routes declare it as a dependency:

    @router.get("/protected")
    async def my_endpoint(user: UserContext = Depends(get_current_user)):
        ...

Security notes:
  - HTTPBearer with auto_error=False lets us return a specific 401 message
    when the Authorization header is absent (instead of FastAPI's generic 403).
  - Credentials are extracted from the header only; never from query params or
    request body.
"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.models.user import UserContext
from security.jwt import validate_token

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserContext:
    """
    FastAPI dependency: validate the Bearer token and return a UserContext.

    Args:
        credentials: Extracted from the Authorization: Bearer <token> header.
                     None when the header is absent.

    Returns:
        UserContext with user_id, email, username, roles, groups.

    Raises:
        HTTPException(401, "Not authenticated")  — missing Authorization header
        HTTPException(401, "Token has expired")  — expired token
        HTTPException(401, "Invalid token")      — bad signature / wrong iss/aud
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return await validate_token(credentials.credentials)
