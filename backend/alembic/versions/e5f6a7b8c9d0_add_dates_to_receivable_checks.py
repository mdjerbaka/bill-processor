"""add sent_date and due_date to receivable_checks

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-20
"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("receivable_checks", sa.Column("sent_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("receivable_checks", sa.Column("due_date", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("receivable_checks", "due_date")
    op.drop_column("receivable_checks", "sent_date")
