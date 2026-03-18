"""add is_permanent to payables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payables", sa.Column("is_permanent", sa.Boolean(), server_default="false", nullable=False))


def downgrade() -> None:
    op.drop_column("payables", "is_permanent")
