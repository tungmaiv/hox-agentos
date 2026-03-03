"""Create local auth tables: local_users, local_groups, local_user_groups,
local_group_roles, local_user_roles.

These 5 tables implement the local username/password authentication path,
parallel to Keycloak SSO. See design doc:
  docs/plans/2026-03-03-phase13-local-auth-design.md

No RLS on these tables — they are admin-only, not user-scoped.

Revision ID: 017
Revises: 016
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. local_users — local user accounts (parallel to Keycloak users)
    op.create_table(
        "local_users",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_local_users_username", "local_users", ["username"], unique=True)
    op.create_index("ix_local_users_email", "local_users", ["email"], unique=True)

    # 2. local_groups — groups that carry role assignments (analogous to Keycloak groups)
    op.create_table(
        "local_groups",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_local_groups_name", "local_groups", ["name"], unique=True)

    # 3. local_user_groups — M2M: user ↔ group membership
    op.create_table(
        "local_user_groups",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("local_users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "group_id",
            UUID(as_uuid=True),
            sa.ForeignKey("local_groups.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # 4. local_group_roles — roles attached to a group
    op.create_table(
        "local_group_roles",
        sa.Column(
            "group_id",
            UUID(as_uuid=True),
            sa.ForeignKey("local_groups.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(64), primary_key=True, nullable=False),
    )

    # 5. local_user_roles — direct role overrides on a user
    op.create_table(
        "local_user_roles",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("local_users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(64), primary_key=True, nullable=False),
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("local_user_roles")
    op.drop_table("local_group_roles")
    op.drop_table("local_user_groups")
    op.drop_index("ix_local_groups_name", table_name="local_groups")
    op.drop_table("local_groups")
    op.drop_index("ix_local_users_email", table_name="local_users")
    op.drop_index("ix_local_users_username", table_name="local_users")
    op.drop_table("local_users")
