"""Add conversation_titles table for per-user custom conversation names

Revision ID: 005
Revises: 004
Create Date: 2026-02-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_titles",
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id", "conversation_id"),
    )
    op.create_index(
        "ix_conversation_titles_user_id",
        "conversation_titles",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_titles_user_id", table_name="conversation_titles")
    op.drop_table("conversation_titles")
