"""
ToolAcl ORM model — per-user, per-tool access control list.

Used by Gate 3 (security/acl.py check_tool_acl).

Design:
- user_id comes from JWT (get_current_user), never from request body
- Default policy: allow (no row = allowed)
- Explicit deny: row with allowed=False
- Explicit allow: row with allowed=True (useful to re-allow after bulk deny)
- Unique constraint on (user_id, tool_name) enforces single policy per user+tool
"""
import sqlalchemy as sa
from sqlalchemy import Boolean, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from uuid import UUID, uuid4

from core.db import Base


class ToolAcl(Base):
    __tablename__ = "tool_acl"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    granted_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )

    __table_args__ = (sa.UniqueConstraint("user_id", "tool_name"),)
