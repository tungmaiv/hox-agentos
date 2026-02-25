"""merge 002 memory and 003 credentials

Revision ID: 9754fd080ee2
Revises: 002, 003
Create Date: 2026-02-25 11:29:44.141124

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9754fd080ee2'
down_revision: Union[str, None] = ('002', '003')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
