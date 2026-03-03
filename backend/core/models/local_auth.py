"""
SQLAlchemy ORM models for local authentication.

Five tables parallel to Keycloak's user/group model:
  - local_users:       local username/password accounts
  - local_groups:      groups that carry role assignments
  - local_user_groups: M2M membership (user ↔ group)
  - local_group_roles: roles attached to a group
  - local_user_roles:  direct role overrides on a user

Design rules:
  - No RLS on these tables — they are admin-only, not user-scoped.
  - No FK on user_id columns pointing to external identity tables —
    users live in Keycloak (or locally) and are validated at Gate 1.
  - FKs between local_* tables use ON DELETE CASCADE for clean teardown.

Role resolution: effective roles = union(group roles, direct user roles).
This mirrors Keycloak's realm_roles claim behavior.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class LocalUser(Base):
    """
    A local user account (parallel to Keycloak user).

    is_active=False blocks login and token validation immediately —
    no token blocklist needed because validate_token() checks this field.
    """

    __tablename__ = "local_users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    # bcrypt hash — never stored or logged as plaintext
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    group_memberships: Mapped[list["LocalUserGroup"]] = relationship(
        "LocalUserGroup", back_populates="user", cascade="all, delete-orphan"
    )
    direct_roles: Mapped[list["LocalUserRole"]] = relationship(
        "LocalUserRole", back_populates="user", cascade="all, delete-orphan"
    )


class LocalGroup(Base):
    """
    A local group — carries role assignments.

    All members of the group inherit the group's roles.
    Analogous to a Keycloak group.
    """

    __tablename__ = "local_groups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    members: Mapped[list["LocalUserGroup"]] = relationship(
        "LocalUserGroup", back_populates="group", cascade="all, delete-orphan"
    )
    roles: Mapped[list["LocalGroupRole"]] = relationship(
        "LocalGroupRole", back_populates="group", cascade="all, delete-orphan"
    )


class LocalUserGroup(Base):
    """M2M association: user ↔ group membership."""

    __tablename__ = "local_user_groups"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("local_users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("local_groups.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Relationships
    user: Mapped["LocalUser"] = relationship("LocalUser", back_populates="group_memberships")
    group: Mapped["LocalGroup"] = relationship("LocalGroup", back_populates="members")


class LocalGroupRole(Base):
    """
    A role attached to a group.

    All members of the group inherit this role via role resolution.
    """

    __tablename__ = "local_group_roles"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("local_groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(64), primary_key=True, nullable=False)

    # Relationship
    group: Mapped["LocalGroup"] = relationship("LocalGroup", back_populates="roles")


class LocalUserRole(Base):
    """
    A direct role override on a user.

    Provides individual role assignments that bypass group membership.
    The effective role set is: union(group roles, direct user roles).
    """

    __tablename__ = "local_user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("local_users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(64), primary_key=True, nullable=False)

    # Relationship
    user: Mapped["LocalUser"] = relationship("LocalUser", back_populates="direct_roles")
