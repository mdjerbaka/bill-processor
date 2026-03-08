"""Service-level unit tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Invoice,
    InvoiceStatus,
    Job,
    JobSource,
    Payable,
    PayableStatus,
    VendorJobMapping,
    AppSetting,
)
from app.services.job_matching_service import JobMatchingService
from app.services.payables_service import PayablesService


# ── Job Matching Service ─────────────────────────────────────────

class TestJobMatchingService:

    async def test_exact_vendor_mapping_auto_assigns(self, db_session: AsyncSession):
        job = Job(name="Kitchen Reno", code="KR-01", source=JobSource.MANUAL, is_active=True)
        db_session.add(job)
        await db_session.flush()

        mapping = VendorJobMapping(
            vendor_name_pattern="Acme Supply",
            job_id=job.id,
            auto_assign=True,
            match_count=0,
        )
        db_session.add(mapping)
        await db_session.flush()

        invoice = Invoice(
            vendor_name="Acme Supply",
            total_amount=500,
            status=InvoiceStatus.EXTRACTED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(invoice)
        await db_session.flush()

        svc = JobMatchingService(db_session)
        suggestions = await svc.match_invoice(invoice)

        assert invoice.status == InvoiceStatus.AUTO_MATCHED
        assert invoice.job_id == job.id
        assert len(suggestions) >= 1

    async def test_no_match_marks_needs_review(self, db_session: AsyncSession):
        invoice = Invoice(
            vendor_name="Unknown Corp",
            total_amount=200,
            status=InvoiceStatus.EXTRACTED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(invoice)
        await db_session.flush()

        svc = JobMatchingService(db_session)
        suggestions = await svc.match_invoice(invoice)

        assert invoice.status == InvoiceStatus.NEEDS_REVIEW
        assert invoice.job_id is None

    async def test_learn_from_assignment_creates_mapping(self, db_session: AsyncSession):
        job = Job(name="Bathroom", source=JobSource.MANUAL, is_active=True)
        db_session.add(job)
        await db_session.flush()

        svc = JobMatchingService(db_session)
        await svc.learn_from_assignment("New Vendor LLC", job.id)
        await db_session.flush()

        from sqlalchemy import select
        result = await db_session.execute(
            select(VendorJobMapping).where(VendorJobMapping.job_id == job.id)
        )
        mapping = result.scalar_one_or_none()
        assert mapping is not None
        assert mapping.vendor_name_pattern == "New Vendor LLC"

    async def test_no_vendor_name_returns_empty(self, db_session: AsyncSession):
        invoice = Invoice(
            vendor_name=None,
            total_amount=100,
            status=InvoiceStatus.EXTRACTED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(invoice)
        await db_session.flush()

        svc = JobMatchingService(db_session)
        suggestions = await svc.match_invoice(invoice)
        assert suggestions == []


# ── Payables Service ─────────────────────────────────────────────

class TestPayablesService:

    async def test_create_payable(self, db_session: AsyncSession):
        inv = Invoice(
            vendor_name="Test",
            total_amount=1500.0,
            due_date=datetime.now(timezone.utc) + timedelta(days=30),
            status=InvoiceStatus.APPROVED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(inv)
        await db_session.flush()

        svc = PayablesService(db_session)
        payable = await svc.create_payable(inv)

        assert payable.amount == 1500.0
        assert payable.status == PayableStatus.OUTSTANDING

    async def test_mark_paid(self, db_session: AsyncSession):
        inv = Invoice(
            vendor_name="V", total_amount=100,
            status=InvoiceStatus.APPROVED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(inv)
        await db_session.flush()

        payable = Payable(
            invoice_id=inv.id, vendor_name="V", amount=100,
            status=PayableStatus.OUTSTANDING,
        )
        db_session.add(payable)
        await db_session.flush()

        svc = PayablesService(db_session)
        result = await svc.mark_paid(payable.id)
        assert result.status == PayableStatus.PAID
        assert result.paid_at is not None

    async def test_summary_calculations(self, db_session: AsyncSession):
        for i, amount in enumerate([500, 300, 200]):
            inv = Invoice(
                vendor_name=f"V{i}", total_amount=amount,
                status=InvoiceStatus.APPROVED,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db_session.add(inv)
            await db_session.flush()
            payable = Payable(
                invoice_id=inv.id, vendor_name=f"V{i}", amount=amount,
                due_date=datetime.now(timezone.utc) + timedelta(days=30),
                status=PayableStatus.OUTSTANDING,
            )
            db_session.add(payable)
        await db_session.flush()

        svc = PayablesService(db_session)
        summary = await svc.get_payables_summary()
        assert summary["total_outstanding"] == 1000.0
        assert summary["count"] == 3

    async def test_real_balance(self, db_session: AsyncSession):
        # Set bank balance
        setting = AppSetting(key="bank_balance", value="5000.0")
        db_session.add(setting)

        inv = Invoice(
            vendor_name="V", total_amount=2000,
            status=InvoiceStatus.APPROVED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(inv)
        await db_session.flush()

        payable = Payable(
            invoice_id=inv.id, vendor_name="V", amount=2000,
            due_date=datetime.now(timezone.utc) + timedelta(days=10),
            status=PayableStatus.OUTSTANDING,
        )
        db_session.add(payable)
        await db_session.flush()

        svc = PayablesService(db_session)
        balance = await svc.get_real_balance()
        assert balance["bank_balance"] == 5000.0
        assert balance["total_outstanding"] == 2000.0
        assert balance["real_available"] == 3000.0
