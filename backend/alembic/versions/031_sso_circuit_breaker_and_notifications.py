"""031_sso_circuit_breaker_and_notifications

Revision ID: a1b2c3d4e5f6
Revises: 617b296e937a
Create Date: 2026-03-15

Creates admin_notifications table for generic admin notification infrastructure.
Adds circuit breaker threshold columns to platform_config table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "617b296e937a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create admin_notifications table
    op.create_table(
        "admin_notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("category", sa.String(50), nullable=False, index=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("metadata_json", sa.Text, nullable=True),
    )

    # Add circuit breaker threshold columns to platform_config
    op.add_column(
        "platform_config",
        sa.Column(
            "cb_failure_threshold",
            sa.Integer,
            nullable=False,
            server_default="5",
        ),
    )
    op.add_column(
        "platform_config",
        sa.Column(
            "cb_recovery_timeout",
            sa.Integer,
            nullable=False,
            server_default="60",
        ),
    )
    op.add_column(
        "platform_config",
        sa.Column(
            "cb_half_open_max_calls",
            sa.Integer,
            nullable=False,
            server_default="1",
        ),
    )


def downgrade() -> None:
    op.drop_column("platform_config", "cb_half_open_max_calls")
    op.drop_column("platform_config", "cb_recovery_timeout")
    op.drop_column("platform_config", "cb_failure_threshold")
    op.drop_table("admin_notifications")
