"""
FastAPI dependencies for authentication and authorization.

get_current_user() is the single entry point for Gate 1 (JWT validation).
get_user_db() combines DB session with RLS activation — use in all user-scoped routes.

All protected routes declare one or both:

    @router.get("/protected")
    async def my_endpoint(
        user: UserContext = Depends(get_current_user),
        session: AsyncSession = Depends(get_user_db),
    ):
        ...

Security notes:
  - HTTPBearer with auto_error=False lets us return a specific 401 message
    when the Authorization header is absent (instead of FastAPI's generic 403).
  - Credentials are extracted from the header only; never from query params or
    request body.
  - get_user_db calls set_rls_user_id before yielding the session, activating
    PostgreSQL RLS migration 016 for all user-scoped queries.
"""
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db, set_rls_user_id
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


async def get_user_db(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency: DB session with RLS user_id set for the authenticated user.

    Calls set_rls_user_id() before yielding the session so that all PostgreSQL
    RLS policies in migration 016 evaluate correctly for this user. Without this,
    the blitz DB role's BYPASSRLS grant means all rows are returned regardless of
    user ownership.

    Use in every route that queries user-scoped tables:
        memory_facts, memory_conversations, user_credentials,
        workflow_runs, memory_episodes, conversation_titles.

    Admin routes that intentionally query across all users should use get_db directly.

    Args:
        user:    Authenticated UserContext from Gate 1 (JWT).
        session: DB session from get_db (overridable in tests).

    Yields:
        AsyncSession with app.user_id set via SET LOCAL.
    """
    await set_rls_user_id(session, user["user_id"])
    yield session
