"""Add channel_accounts and channel_sessions tables.

Tables for multi-channel integration: maps external platform users (Telegram,
WhatsApp, MS Teams) to Blitz users via pairing codes, and tracks per-chat
sessions with conversation IDs.

Revision ID: 013
Revises: 012
Create Date: 2026-02-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "channel_accounts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("external_user_id", sa.String(256), nullable=False),
        sa.Column("display_name", sa.String(256), nullable=True),
        sa.Column("pairing_code", sa.String(16), nullable=True),
        sa.Column("pairing_expires", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_paired", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "metadata_json",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel", "external_user_id", name="uq_channel_external_user"),
    )
    op.create_index(op.f("ix_channel_accounts_user_id"), "channel_accounts", ["user_id"])

    op.create_table(
        "channel_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("channel_account_id", sa.UUID(), nullable=False),
        sa.Column("external_chat_id", sa.String(256), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["channel_account_id"],
            ["channel_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("channel_account_id", "external_chat_id", name="uq_account_chat"),
    )


def downgrade() -> None:
    op.drop_table("channel_sessions")
    op.drop_index(op.f("ix_channel_accounts_user_id"), table_name="channel_accounts")
    op.drop_table("channel_accounts")
