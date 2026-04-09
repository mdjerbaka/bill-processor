"""add included_in_cashflow to recurring_bills

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'h8c9d0e1f2g3'
down_revision = 'g7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('recurring_bills', sa.Column('included_in_cashflow', sa.Boolean(), server_default='1', nullable=False))


def downgrade() -> None:
    op.drop_column('recurring_bills', 'included_in_cashflow')
