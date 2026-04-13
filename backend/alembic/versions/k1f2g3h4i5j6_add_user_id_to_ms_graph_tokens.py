"""Add user_id to ms_graph_tokens for per-user MS 365 connections.

Revision ID: k1f2g3h4i5j6
Revises: j0e1f2g3h4i5
Create Date: 2026-04-13
"""

from alembic import op
import sqlalchemy as sa

revision = "k1f2g3h4i5j6"
down_revision = "j0e1f2g3h4i5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ms_graph_tokens", sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.create_index("ix_ms_graph_tokens_user_id", "ms_graph_tokens", ["user_id"])
    # Assign existing token to santimaw (user_id=2) who originally connected it
    op.execute("UPDATE ms_graph_tokens SET user_id = 2 WHERE user_id IS NULL")


def downgrade() -> None:
    op.drop_index("ix_ms_graph_tokens_user_id", table_name="ms_graph_tokens")
    op.drop_column("ms_graph_tokens", "user_id")
