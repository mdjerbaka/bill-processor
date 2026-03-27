"""Add included_in_cashflow to payables, qbo_invoice_id to receivable_checks,
invoice_number/job_name/qbo fields to payables for invoice decoupling.

Revision ID: a1b2c3d4e5f7
Revises: f6a7b8c9d0e1
Create Date: 2026-03-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f7"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Phase 1: Payable cash flow toggle
    op.add_column(
        "payables",
        sa.Column("included_in_cashflow", sa.Boolean(), server_default="1", nullable=False),
    )

    # Phase 2: QB invoice sync dedup field for receivables
    op.add_column(
        "receivable_checks",
        sa.Column("qbo_invoice_id", sa.String(100), nullable=True),
    )

    # Phase 4: Store invoice/job/QB data directly on payable before deleting invoice
    op.add_column(
        "payables",
        sa.Column("invoice_number", sa.String(200), nullable=True),
    )
    op.add_column(
        "payables",
        sa.Column("job_name", sa.String(500), nullable=True),
    )
    op.add_column(
        "payables",
        sa.Column("qbo_bill_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "payables",
        sa.Column("qbo_vendor_id", sa.String(100), nullable=True),
    )

    # Backfill existing payables with data from linked invoices
    op.execute("""
        UPDATE payables
        SET invoice_number = (
            SELECT invoices.invoice_number FROM invoices WHERE invoices.id = payables.invoice_id
        ),
        job_name = (
            SELECT jobs.name FROM invoices
            LEFT JOIN jobs ON invoices.job_id = jobs.id
            WHERE invoices.id = payables.invoice_id
        ),
        qbo_bill_id = (
            SELECT invoices.qbo_bill_id FROM invoices WHERE invoices.id = payables.invoice_id
        ),
        qbo_vendor_id = (
            SELECT invoices.qbo_vendor_id FROM invoices WHERE invoices.id = payables.invoice_id
        )
        WHERE payables.invoice_id IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_column("payables", "qbo_vendor_id")
    op.drop_column("payables", "qbo_bill_id")
    op.drop_column("payables", "job_name")
    op.drop_column("payables", "invoice_number")
    op.drop_column("receivable_checks", "qbo_invoice_id")
    op.drop_column("payables", "included_in_cashflow")
