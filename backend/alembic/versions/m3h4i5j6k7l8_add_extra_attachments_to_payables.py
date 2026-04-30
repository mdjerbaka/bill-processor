"""add extra_attachments JSON column to payables

Revision ID: m3h4i5j6k7l8
Revises: l2g3h4i5j6k7
Create Date: 2026-04-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m3h4i5j6k7l8"
down_revision: Union[str, None] = "l2g3h4i5j6k7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payables",
        sa.Column("extra_attachments", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payables", "extra_attachments")
