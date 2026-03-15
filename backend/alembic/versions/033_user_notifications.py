"""033_user_notifications

Revision ID: 033_user_notifications
Revises: 032_storage_tables
Create Date: 2026-03-16

Creates user_notifications table for per-user share and system event notifications (Phase 28, STOR-04).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "033_user_notifications"
down_revision: Union[str, None] = "032_storage_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_notifications",
        sa.Column(
            "id",
            PGUUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("user_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_user_notifications_user_id",
        "user_notifications",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_notifications_user_id", table_name="user_notifications")
    op.drop_table("user_notifications")
