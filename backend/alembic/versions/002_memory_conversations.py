"""Add memory_conversations table

Revision ID: 002
Revises: 001
Create Date: 2026-02-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("conversation_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("role", sa.Text(), nullable=False),  # "user" | "assistant" | "tool"
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    # Composite index for the load_recent_turns query pattern
    op.create_index(
        "ix_memory_conversations_user_conversation",
        "memory_conversations",
        ["user_id", "conversation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_memory_conversations_user_conversation")
    op.drop_table("memory_conversations")
