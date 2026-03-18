"""make payable invoice_id nullable

Revision ID: 8d5e4f3a2b1c
Revises: 7c4b9e3f2a1d
Create Date: 2026-03-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d5e4f3a2b1c'
down_revision: str = '7c4b9e3f2a1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('payables', 'invoice_id',
                     existing_type=sa.Integer(),
                     nullable=True)


def downgrade() -> None:
    op.alter_column('payables', 'invoice_id',
                     existing_type=sa.Integer(),
                     nullable=False)
