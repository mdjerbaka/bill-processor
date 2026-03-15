"""add_payroll_subcontractor_credit_danger_enums

Revision ID: 6b3a8f2c1d9e
Revises: 513185f436be
Create Date: 2026-03-16 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '6b3a8f2c1d9e'
down_revision: Union[str, None] = '513185f436be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE billcategory ADD VALUE IF NOT EXISTS 'PAYROLL'")
    op.execute("ALTER TYPE billcategory ADD VALUE IF NOT EXISTS 'SUBCONTRACTOR'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'BILL_CREDIT_DANGER'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from enum types.
    pass
