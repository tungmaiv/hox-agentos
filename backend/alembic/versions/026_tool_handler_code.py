"""add handler_code column to tool_definitions

Revision ID: 026
Revises: 025
Create Date: 2026-03-10

Phase 23-SKBLD-03: Tool artifact builder generates a Python handler stub.
Adds handler_code TEXT NULL to tool_definitions for storing generated handler code.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tool_definitions",
        sa.Column("handler_code", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tool_definitions", "handler_code")
