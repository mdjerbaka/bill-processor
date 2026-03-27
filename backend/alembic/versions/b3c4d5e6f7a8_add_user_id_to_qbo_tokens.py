"""Add user_id to qbo_tokens for per-user QB connections.

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f7
Create Date: 2026-03-26
"""

from alembic import op
import sqlalchemy as sa

revision = "b3c4d5e6f7a8"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("qbo_tokens", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.create_index("ix_qbo_tokens_user_id", "qbo_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_qbo_tokens_user_id", table_name="qbo_tokens")
    op.drop_column("qbo_tokens", "user_id")
