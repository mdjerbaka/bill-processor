"""add_weekly_frequency_and_nullable_due_day

Revision ID: 7c4b9e3f2a1d
Revises: 6b3a8f2c1d9e
Create Date: 2026-03-17 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c4b9e3f2a1d'
down_revision: Union[str, None] = '6b3a8f2c1d9e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE billfrequency ADD VALUE IF NOT EXISTS 'WEEKLY'")
    op.alter_column('recurring_bills', 'due_day_of_month',
                     existing_type=sa.Integer(),
                     nullable=True)


def downgrade() -> None:
    op.alter_column('recurring_bills', 'due_day_of_month',
                     existing_type=sa.Integer(),
                     nullable=False)
