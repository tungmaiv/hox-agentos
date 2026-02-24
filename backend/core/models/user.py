"""
UserContext — internal data class for the authenticated caller.

Populated by Gate 1 (JWT validation in security/jwt.py) and threaded through
all agent, tool, and memory operations. Never returned directly to the frontend
— only structured tool results are returned.

This is intentionally a TypedDict (not Pydantic BaseModel) because it is an
internal data structure passed between functions, not a serializable API schema.
"""
from typing import TypedDict
from uuid import UUID


class UserContext(TypedDict):
    user_id: UUID  # from JWT `sub`
    email: str  # from JWT `email`
    username: str  # from JWT `preferred_username`
    roles: list[str]  # from JWT `realm_access.roles`
    groups: list[str]  # from JWT `groups` (full paths, e.g. "/tech")
