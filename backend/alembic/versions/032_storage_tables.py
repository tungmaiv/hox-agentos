"""032_storage_tables

Revision ID: 032_storage_tables
Revises: a1b2c3d4e5f6
Create Date: 2026-03-16

Creates storage_folders, storage_files, and storage_shares tables for Phase 28
MinIO-backed file storage (STOR-01, STOR-02, STOR-03, STOR-04).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "032_storage_tables"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. storage_folders — must be created before storage_files (FK dependency)
    op.create_table(
        "storage_folders",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("owner_user_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "parent_folder_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("storage_folders.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_storage_folders_owner_user_id",
        "storage_folders",
        ["owner_user_id"],
    )

    # 2. storage_files — references storage_folders
    op.create_table(
        "storage_files",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("owner_user_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column(
            "folder_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("storage_folders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("object_key", sa.String(500), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("mime_type", sa.String(200), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("in_memory", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_storage_files_owner_user_id",
        "storage_files",
        ["owner_user_id"],
    )
    op.create_index(
        "ix_storage_files_content_hash",
        "storage_files",
        ["content_hash"],
    )

    # 3. storage_shares — references both storage_files and storage_folders
    op.create_table(
        "storage_shares",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "file_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("storage_files.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "folder_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("storage_folders.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("shared_with_user_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("shared_by_user_id", PGUUID(as_uuid=True), nullable=False),
        sa.Column("permission", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_storage_shares_shared_with_user_id",
        "storage_shares",
        ["shared_with_user_id"],
    )


def downgrade() -> None:
    op.drop_table("storage_shares")
    op.drop_table("storage_files")
    op.drop_table("storage_folders")
