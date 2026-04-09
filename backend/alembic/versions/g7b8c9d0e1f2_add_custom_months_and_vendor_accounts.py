"""add custom_months and vendor_accounts

Revision ID: g7b8c9d0e1f2
Revises: b3c4d5e6f7a8
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision: str = 'g7b8c9d0e1f2'
down_revision: Union[str, None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add custom_months column to recurring_bills
    op.add_column('recurring_bills', sa.Column('custom_months', JSON, nullable=True))

    # Add 'custom' to bill_frequency enum
    op.execute("ALTER TYPE billfrequency ADD VALUE IF NOT EXISTS 'custom'")

    # Add 'email_no_attachment' to notification_type enum
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'email_no_attachment'")

    # Create vendor_accounts table
    op.create_table(
        'vendor_accounts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('vendor_name', sa.String(500), nullable=False),
        sa.Column('account_info', sa.String(500), nullable=True),
        sa.Column('as_of_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('amount', sa.Float(), nullable=False, server_default='0'),
        sa.Column('notes_due_dates', sa.Text(), nullable=True),
        sa.Column('links', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_vendor_accounts_user_id', 'vendor_accounts', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_vendor_accounts_user_id', table_name='vendor_accounts')
    op.drop_table('vendor_accounts')
    op.drop_column('recurring_bills', 'custom_months')
