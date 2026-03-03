"""
Pydantic v2 request/response schemas for local authentication.

Covers:
  - Login (LocalLoginRequest / LocalLoginResponse)
  - User CRUD (LocalUserCreate, LocalUserUpdate, LocalUserResponse)
  - Group CRUD (LocalGroupCreate, LocalGroupUpdate, LocalGroupResponse)
  - Role + group assignment helpers (RoleAssignment, GroupAssignment)

Design rules:
  - password_hash is NEVER included in any response schema.
  - resolved_roles in LocalUserResponse is the union(group roles, direct user roles),
    computed by security.local_auth.resolve_user_roles().
  - GroupBrief is a lightweight sub-schema embedded in LocalUserResponse.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator

from security.local_auth import validate_password_complexity


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


class LocalLoginRequest(BaseModel):
    """POST /api/auth/local/token request body."""

    username: str
    password: str


class LocalLoginResponse(BaseModel):
    """POST /api/auth/local/token response body."""

    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------


class LocalUserCreate(BaseModel):
    """POST /api/admin/local/users request body."""

    username: str
    email: EmailStr
    password: str
    group_ids: list[UUID] = []
    role_names: list[str] = []

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 64:
            raise ValueError("username must be 3–64 characters")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password complexity."""
        validate_password_complexity(v)
        return v


class LocalUserUpdate(BaseModel):
    """PUT /api/admin/local/users/{id} request body — all fields optional."""

    username: str | None = None
    email: EmailStr | None = None
    password: str | None = None
    is_active: bool | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if len(v) < 3 or len(v) > 64:
            raise ValueError("username must be 3–64 characters")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str | None) -> str | None:
        """Validate password complexity when provided."""
        if v is None:
            return v
        validate_password_complexity(v)
        return v


class GroupBrief(BaseModel):
    """Lightweight group info embedded in LocalUserResponse."""

    id: UUID
    name: str

    model_config = {"from_attributes": True}


class LocalUserResponse(BaseModel):
    """Response schema for user detail and list endpoints."""

    id: UUID
    username: str
    email: str
    is_active: bool
    groups: list[GroupBrief]
    roles: list[str]  # resolved: union(group roles, direct user roles)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Group CRUD
# ---------------------------------------------------------------------------


class LocalGroupCreate(BaseModel):
    """POST /api/admin/local/groups request body."""

    name: str
    description: str = ""
    roles: list[str] = []

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 64:
            raise ValueError("name must be 3–64 characters")
        return v


class LocalGroupUpdate(BaseModel):
    """PUT /api/admin/local/groups/{id} request body — all fields optional."""

    name: str | None = None
    description: str | None = None
    roles: list[str] | None = None  # When set, REPLACES the entire role set

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if len(v) < 3 or len(v) > 64:
            raise ValueError("name must be 3–64 characters")
        return v


class LocalGroupResponse(BaseModel):
    """Response schema for group detail and list endpoints."""

    id: UUID
    name: str
    description: str
    roles: list[str]
    member_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Role + group assignment helpers
# ---------------------------------------------------------------------------


class RoleAssignment(BaseModel):
    """Body for POST /api/admin/local/users/{id}/roles."""

    roles: list[str]


class GroupAssignment(BaseModel):
    """Body for POST /api/admin/local/users/{id}/groups."""

    group_ids: list[UUID]
