"""add included_in_cashflow to bill_occurrences

Revision ID: 9e6f5a4b3c2d
Revises: 8d5e4f3a2b1c
Create Date: 2026-03-18 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e6f5a4b3c2d'
down_revision: str = '8d5e4f3a2b1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bill_occurrences',
                  sa.Column('included_in_cashflow', sa.Boolean(),
                            server_default='1', nullable=False))


def downgrade() -> None:
    op.drop_column('bill_occurrences', 'included_in_cashflow')
