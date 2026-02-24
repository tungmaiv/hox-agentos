"""
Common Pydantic response schemas shared across the application.
"""
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    detail: str
    permission_required: str | None = None
    user_roles: list[str] | None = None
    hint: str | None = None
