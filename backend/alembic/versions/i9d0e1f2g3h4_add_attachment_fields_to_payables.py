"""add attachment_path and attachment_filename to payables, add included_in_cashflow to vendor_accounts

Revision ID: i9d0e1f2g3h4
Revises: h8c9d0e1f2g3
Create Date: 2026-04-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'i9d0e1f2g3h4'
down_revision = 'h8c9d0e1f2g3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('payables', sa.Column('attachment_path', sa.String(1000), nullable=True))
    op.add_column('payables', sa.Column('attachment_filename', sa.String(500), nullable=True))
    op.add_column('vendor_accounts', sa.Column('included_in_cashflow', sa.Boolean(), server_default='1', nullable=False))


def downgrade() -> None:
    op.drop_column('vendor_accounts', 'included_in_cashflow')
    op.drop_column('payables', 'attachment_filename')
    op.drop_column('payables', 'attachment_path')
