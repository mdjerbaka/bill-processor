"""add payment_out table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    payment_method_enum = sa.Enum(
        "check", "ach", "debit", "online", "wire", "other",
        name="paymentmethod",
    )
    payment_out_status_enum = sa.Enum(
        "outstanding", "cleared",
        name="paymentoutstatus",
    )

    op.create_table(
        "payments_out",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("payment_method", payment_method_enum, server_default="other", nullable=False),
        sa.Column("check_number", sa.String(50), nullable=True),
        sa.Column("vendor_name", sa.String(500), nullable=False),
        sa.Column("job_name", sa.String(500), nullable=True),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("payment_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", payment_out_status_enum, server_default="outstanding", nullable=False),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payable_id", sa.Integer(), sa.ForeignKey("payables.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("payments_out")
    sa.Enum(name="paymentmethod").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="paymentoutstatus").drop(op.get_bind(), checkfirst=True)
