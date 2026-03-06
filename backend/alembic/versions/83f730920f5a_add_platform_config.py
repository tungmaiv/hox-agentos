"""add_platform_config

Revision ID: 83f730920f5a
Revises: 020
Create Date: 2026-03-06 15:33:14.911199

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '83f730920f5a'
down_revision: Union[str, None] = '020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'platform_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('keycloak_url', sa.String(length=500), nullable=True),
        sa.Column('keycloak_realm', sa.String(length=200), nullable=True),
        sa.Column('keycloak_client_id', sa.String(length=200), nullable=True),
        sa.Column('keycloak_client_secret_encrypted', sa.Text(), nullable=True),
        sa.Column('keycloak_ca_cert', sa.String(length=500), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('platform_config')
