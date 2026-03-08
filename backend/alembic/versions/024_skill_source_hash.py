"""add source_hash column to skill_definitions

Revision ID: 024
Revises: 023
Create Date: 2026-03-08

Phase 21-SKSEC-03: SHA-256 hash for upstream change detection.
Stores the SHA-256 hash of the last-fetched source_url content.
Used by the daily check_skill_updates Celery task to detect upstream changes.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "skill_definitions",
        sa.Column("source_hash", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("skill_definitions", "source_hash")
