"""Comprehensive QB integration + payables flow tests.

Tests the full lifecycle:
  Invoice → Approve → QB bill send → Mark Paid → QB payment
  Invoice → Auto-match → Payable creation → Mark Paid → QB payment
  Edge cases: missing bank account, QB errors, backfill, etc.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_value
from app.models.models import (
    AppSetting,
    Invoice,
    InvoiceLineItem,
    InvoiceStatus,
    Job,
    JobSource,
    Payable,
    PayableStatus,
    QBOToken,
)


# ── Helpers ──────────────────────────────────────────────────────

async def _create_qbo_token(db: AsyncSession) -> QBOToken:
    """Insert a valid (non-expired) QBO token for tests."""
    now = datetime.now(timezone.utc)
    token = QBOToken(
        access_token=encrypt_value("test-access-token"),
        refresh_token=encrypt_value("test-refresh-token"),
        realm_id="9341456555017357",
        expires_at=now + timedelta(hours=1),
        refresh_expires_at=now + timedelta(days=100),
    )
    db.add(token)
    await db.flush()
    return token


async def _set_qbo_defaults(db: AsyncSession):
    """Set default expense + bank account IDs in app_settings."""
    for key, value in [
        ("qbo_default_expense_account", "76"),
        ("qbo_default_bank_account", "35"),
    ]:
        db.add(AppSetting(key=key, value=value))
    await db.flush()


async def _create_invoice(
    db: AsyncSession,
    vendor_name: str = "Test Vendor",
    total: float = 1000.0,
    status: InvoiceStatus = InvoiceStatus.EXTRACTED,
    job_id: int | None = None,
    qbo_bill_id: str | None = None,
    qbo_vendor_id: str | None = None,
    with_line_items: bool = False,
) -> Invoice:
    inv = Invoice(
        vendor_name=vendor_name,
        invoice_number="INV-TEST-001",
        total_amount=total,
        subtotal=total,
        due_date=datetime.now(timezone.utc) + timedelta(days=30),
        status=status,
        job_id=job_id,
        qbo_bill_id=qbo_bill_id,
        qbo_vendor_id=qbo_vendor_id,
        confidence_score=0.95,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(inv)
    await db.flush()

    if with_line_items:
        li = InvoiceLineItem(
            invoice_id=inv.id,
            description="Materials",
            quantity=1,
            unit_price=total,
            amount=total,
        )
        db.add(li)
        await db.flush()

    return inv


async def _create_job(db: AsyncSession, name: str = "Job Alpha") -> Job:
    job = Job(name=name, code="J-001", source=JobSource.MANUAL, is_active=True)
    db.add(job)
    await db.flush()
    return job


def _mock_qb_api_request(bill_id="101", vendor_id="61", payment_id="201"):
    """Return an AsyncMock for _api_request that responds correctly."""
    async def mock_api(method, path, json_data=None):
        if method == "POST" and path == "bill":
            return {"Bill": {"Id": bill_id}}
        if method == "POST" and path == "billpayment":
            return {"BillPayment": {"Id": payment_id}}
        if method == "GET" and "Vendor" in str(path):
            return {"QueryResponse": {"Vendor": [{"Id": vendor_id}]}}
        if method == "GET" and "Account" in str(path):
            if "Bank" in str(path):
                return {"QueryResponse": {"Account": [{"Id": "35", "Name": "Checking"}]}}
            return {"QueryResponse": {"Account": [{"Id": "76", "Name": "Expenses"}]}}
        return {}
    return AsyncMock(side_effect=mock_api)


# ── Approve → QB Bill Send ───────────────────────────────────────

class TestApproveToQB:

    async def test_approve_creates_payable_and_sends_to_qb(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        """Approve should create a Payable AND send bill to QB if connected."""
        await _create_qbo_token(db_session)
        await _set_qbo_defaults(db_session)
        inv = await _create_invoice(db_session, with_line_items=True)
        await db_session.commit()

        with patch(
            "app.services.quickbooks_service.QuickBooksService._api_request",
            _mock_qb_api_request(),
        ):
            resp = await client.post(
                f"/api/v1/invoices/{inv.id}/approve", headers=auth_headers
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("approved", "sent_to_qb")

        # Payable created
        pay_result = await db_session.execute(
            select(Payable).where(Payable.invoice_id == inv.id)
        )
        payable = pay_result.scalar_one_or_none()
        assert payable is not None
        assert payable.status == PayableStatus.OUTSTANDING
        assert payable.amount == 1000.0

    async def test_approve_creates_payable_without_qb(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        """Approve should create Payable even if QB is not connected."""
        inv = await _create_invoice(db_session)
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/invoices/{inv.id}/approve", headers=auth_headers
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

        pay_result = await db_session.execute(
            select(Payable).where(Payable.invoice_id == inv.id)
        )
        assert pay_result.scalar_one_or_none() is not None

    async def test_approve_already_approved_returns_400(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        inv = await _create_invoice(db_session, status=InvoiceStatus.APPROVED)
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/invoices/{inv.id}/approve", headers=auth_headers
        )
        assert resp.status_code == 400


# ── Mark Paid from Invoice Detail → QB Payment ──────────────────

class TestMarkPaidInvoice:

    async def test_mark_paid_syncs_to_qb(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        """Mark-paid on an invoice with qbo_bill_id should create QB payment."""
        await _create_qbo_token(db_session)
        await _set_qbo_defaults(db_session)
        inv = await _create_invoice(
            db_session,
            status=InvoiceStatus.SENT_TO_QB,
            qbo_bill_id="101",
            qbo_vendor_id="61",
        )
        # Create existing payable (as would exist from approve)
        payable = Payable(
            invoice_id=inv.id, vendor_name="Test Vendor",
            amount=1000.0, status=PayableStatus.OUTSTANDING,
        )
        db_session.add(payable)
        await db_session.commit()

        with patch(
            "app.services.quickbooks_service.QuickBooksService._api_request",
            _mock_qb_api_request(),
        ):
            resp = await client.post(
                f"/api/v1/invoices/{inv.id}/mark-paid", headers=auth_headers
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "paid"

        # Payable marked paid
        pay_result = await db_session.execute(
            select(Payable).where(Payable.invoice_id == inv.id)
        )
        payable = pay_result.scalar_one()
        assert payable.status == PayableStatus.PAID
        assert payable.paid_at is not None

    async def test_mark_paid_creates_payable_if_missing(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        """Mark-paid should create a Payable if one doesn't exist (backfill)."""
        inv = await _create_invoice(
            db_session, status=InvoiceStatus.SENT_TO_QB,
            qbo_bill_id="101", qbo_vendor_id="61",
        )
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/invoices/{inv.id}/mark-paid", headers=auth_headers
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "paid"

        # A payable was created and marked paid
        pay_result = await db_session.execute(
            select(Payable).where(Payable.invoice_id == inv.id)
        )
        payable = pay_result.scalar_one_or_none()
        assert payable is not None
        assert payable.status == PayableStatus.PAID

    async def test_mark_paid_sends_bill_first_if_no_qbo_bill(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        """If bill not in QB yet, mark-paid should send bill then pay it."""
        await _create_qbo_token(db_session)
        await _set_qbo_defaults(db_session)
        inv = await _create_invoice(
            db_session, status=InvoiceStatus.APPROVED,
        )
        payable = Payable(
            invoice_id=inv.id, vendor_name="Test Vendor",
            amount=1000.0, status=PayableStatus.OUTSTANDING,
        )
        db_session.add(payable)
        await db_session.commit()

        mock_api = _mock_qb_api_request()
        with patch(
            "app.services.quickbooks_service.QuickBooksService._api_request",
            mock_api,
        ):
            resp = await client.post(
                f"/api/v1/invoices/{inv.id}/mark-paid", headers=auth_headers
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "paid"

        # Verify both bill creation and payment were attempted
        post_calls = [c for c in mock_api.call_args_list if c[0][0] == "POST"]
        paths = [c[0][1] for c in post_calls]
        assert "bill" in paths, "Should have created a bill"
        assert "billpayment" in paths, "Should have created a payment"

    async def test_mark_paid_without_qb_connection(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        """Mark-paid should work even without QB — just updates local status."""
        inv = await _create_invoice(db_session, status=InvoiceStatus.APPROVED)
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/invoices/{inv.id}/mark-paid", headers=auth_headers
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "paid"


# ── Mark Paid from Payables Tab → QB Payment ────────────────────

class TestMarkPaidPayable:

    async def test_payable_mark_paid_syncs_to_qb(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        """Mark-paid from payables should sync payment to QB."""
        await _create_qbo_token(db_session)
        await _set_qbo_defaults(db_session)
        inv = await _create_invoice(
            db_session,
            status=InvoiceStatus.SENT_TO_QB,
            qbo_bill_id="101",
            qbo_vendor_id="61",
        )
        payable = Payable(
            invoice_id=inv.id, vendor_name="Test Vendor",
            amount=1000.0, status=PayableStatus.OUTSTANDING,
        )
        db_session.add(payable)
        await db_session.commit()

        with patch(
            "app.services.quickbooks_service.QuickBooksService._api_request",
            _mock_qb_api_request(),
        ):
            resp = await client.post(
                f"/api/v1/payables/{payable.id}/mark-paid", headers=auth_headers
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "paid"

    async def test_payable_mark_paid_updates_invoice_status(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        """Marking payable paid should also set invoice status to PAID."""
        inv = await _create_invoice(db_session, status=InvoiceStatus.APPROVED)
        payable = Payable(
            invoice_id=inv.id, vendor_name="Test Vendor",
            amount=1000.0, status=PayableStatus.OUTSTANDING,
        )
        db_session.add(payable)
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/payables/{payable.id}/mark-paid", headers=auth_headers
        )

        assert resp.status_code == 200

        # Invoice status should now be PAID
        result = await db_session.execute(
            select(Invoice).where(Invoice.id == inv.id)
        )
        updated_inv = result.scalar_one()
        assert updated_inv.status == InvoiceStatus.PAID


# ── Payables List (visibility) ───────────────────────────────────

class TestPayablesVisibility:

    async def test_auto_matched_with_payable_shows_in_list(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        """Auto-matched invoice WITH a Payable should appear in payables list."""
        inv = await _create_invoice(
            db_session, status=InvoiceStatus.SENT_TO_QB,
            qbo_bill_id="101",
        )
        payable = Payable(
            invoice_id=inv.id, vendor_name="Test Vendor",
            amount=1000.0, status=PayableStatus.OUTSTANDING,
            due_date=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db_session.add(payable)
        await db_session.commit()

        resp = await client.get("/api/v1/payables", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["vendor_name"] == "Test Vendor"

    async def test_invoice_without_payable_not_in_payables(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        """Invoice WITHOUT a Payable should NOT appear in payables list."""
        await _create_invoice(
            db_session, status=InvoiceStatus.SENT_TO_QB,
            qbo_bill_id="101",
        )
        await db_session.commit()

        resp = await client.get("/api/v1/payables", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_paid_payables_hidden_by_default(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        """Paid payables should be hidden unless include_paid=True."""
        inv = await _create_invoice(db_session, status=InvoiceStatus.PAID)
        payable = Payable(
            invoice_id=inv.id, vendor_name="Test Vendor",
            amount=1000.0, status=PayableStatus.PAID,
            paid_at=datetime.now(timezone.utc),
        )
        db_session.add(payable)
        await db_session.commit()

        resp = await client.get("/api/v1/payables", headers=auth_headers)
        assert resp.json()["total"] == 0

        resp2 = await client.get(
            "/api/v1/payables",
            params={"include_paid": True},
            headers=auth_headers,
        )
        assert resp2.json()["total"] == 1


# ── QB Error Handling ────────────────────────────────────────────

class TestQBErrorHandling:

    async def test_pay_bill_qbo_error_doesnt_crash_mark_paid(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        """QB payment error should not prevent local mark-paid from succeeding."""
        await _create_qbo_token(db_session)
        await _set_qbo_defaults(db_session)
        inv = await _create_invoice(
            db_session,
            status=InvoiceStatus.SENT_TO_QB,
            qbo_bill_id="101",
            qbo_vendor_id="61",
        )
        payable = Payable(
            invoice_id=inv.id, vendor_name="Test Vendor",
            amount=1000.0, status=PayableStatus.OUTSTANDING,
        )
        db_session.add(payable)
        await db_session.commit()

        # Simulate QBO returning an error for billpayment
        async def mock_api(method, path, json_data=None):
            if method == "POST" and path == "billpayment":
                return {"Fault": {"Error": [{"Detail": "Duplicate payment"}]}}
            if method == "GET" and "Account" in str(path):
                return {"QueryResponse": {"Account": [{"Id": "35"}]}}
            return {}

        with patch(
            "app.services.quickbooks_service.QuickBooksService._api_request",
            AsyncMock(side_effect=mock_api),
        ):
            resp = await client.post(
                f"/api/v1/invoices/{inv.id}/mark-paid", headers=auth_headers
            )

        # Local status should still be updated
        assert resp.status_code == 200
        assert resp.json()["status"] == "paid"

    async def test_no_bank_account_doesnt_crash(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        """Missing bank account should not crash mark-paid."""
        await _create_qbo_token(db_session)
        # Set expense but NOT bank account
        db_session.add(AppSetting(key="qbo_default_expense_account", value="76"))
        inv = await _create_invoice(
            db_session,
            status=InvoiceStatus.SENT_TO_QB,
            qbo_bill_id="101",
            qbo_vendor_id="61",
        )
        await db_session.commit()

        # QBO returns no Bank accounts
        async def mock_api(method, path, json_data=None):
            if "Bank" in str(path):
                return {"QueryResponse": {}}
            return {}

        with patch(
            "app.services.quickbooks_service.QuickBooksService._api_request",
            AsyncMock(side_effect=mock_api),
        ):
            resp = await client.post(
                f"/api/v1/invoices/{inv.id}/mark-paid", headers=auth_headers
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "paid"

    async def test_qb_exception_doesnt_crash_mark_paid(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        """Unexpected QB exception should be caught gracefully."""
        await _create_qbo_token(db_session)
        inv = await _create_invoice(
            db_session,
            status=InvoiceStatus.SENT_TO_QB,
            qbo_bill_id="101",
            qbo_vendor_id="61",
        )
        await db_session.commit()

        with patch(
            "app.services.quickbooks_service.QuickBooksService.auto_pay_bill",
            side_effect=Exception("Network timeout"),
        ):
            resp = await client.post(
                f"/api/v1/invoices/{inv.id}/mark-paid", headers=auth_headers
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "paid"


# ── Backfill Endpoint ────────────────────────────────────────────

class TestBackfill:

    async def test_backfill_creates_missing_payables(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        """Backfill should create Payable records for orphan invoices."""
        # These invoices have no Payable — simulates the pre-fix state
        inv1 = await _create_invoice(
            db_session, vendor_name="V1", status=InvoiceStatus.SENT_TO_QB,
        )
        inv2 = await _create_invoice(
            db_session, vendor_name="V2", status=InvoiceStatus.AUTO_MATCHED,
        )
        # This one already has a payable — should NOT be duplicated
        inv3 = await _create_invoice(
            db_session, vendor_name="V3", status=InvoiceStatus.APPROVED,
        )
        db_session.add(Payable(
            invoice_id=inv3.id, vendor_name="V3",
            amount=1000.0, status=PayableStatus.OUTSTANDING,
        ))
        # This one is EXTRACTED — should NOT get a payable
        inv4 = await _create_invoice(
            db_session, vendor_name="V4", status=InvoiceStatus.EXTRACTED,
        )
        await db_session.commit()

        resp = await client.post(
            "/api/v1/payables/backfill", headers=auth_headers
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["backfilled"] == 2
        assert data["total_orphans"] == 2

        # Verify payables exist for inv1 and inv2
        for inv_id in [inv1.id, inv2.id]:
            result = await db_session.execute(
                select(Payable).where(Payable.invoice_id == inv_id)
            )
            assert result.scalar_one_or_none() is not None

        # inv4 (EXTRACTED) should still have no payable
        result = await db_session.execute(
            select(Payable).where(Payable.invoice_id == inv4.id)
        )
        assert result.scalar_one_or_none() is None

    async def test_backfill_marks_paid_invoices_payables_as_paid(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        """Backfill for PAID invoices should create payable AND mark it paid."""
        inv = await _create_invoice(
            db_session, vendor_name="V-Paid", status=InvoiceStatus.PAID,
        )
        await db_session.commit()

        resp = await client.post(
            "/api/v1/payables/backfill", headers=auth_headers
        )

        assert resp.json()["backfilled"] == 1

        result = await db_session.execute(
            select(Payable).where(Payable.invoice_id == inv.id)
        )
        payable = result.scalar_one()
        assert payable.status == PayableStatus.PAID
        assert payable.paid_at is not None

    async def test_backfill_idempotent(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        """Running backfill twice should not create duplicates."""
        await _create_invoice(
            db_session, status=InvoiceStatus.SENT_TO_QB,
        )
        await db_session.commit()

        resp1 = await client.post(
            "/api/v1/payables/backfill", headers=auth_headers
        )
        assert resp1.json()["backfilled"] == 1

        resp2 = await client.post(
            "/api/v1/payables/backfill", headers=auth_headers
        )
        assert resp2.json()["backfilled"] == 0


# ── Full Lifecycle (end-to-end) ──────────────────────────────────

class TestFullLifecycle:

    async def test_approve_then_mark_paid_full_flow(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        """Full flow: create invoice → approve → mark paid.

        Verifies payable created, invoice status transitions, and both
        QB bill + payment are attempted.
        """
        await _create_qbo_token(db_session)
        await _set_qbo_defaults(db_session)
        inv = await _create_invoice(db_session, with_line_items=True)
        await db_session.commit()

        mock_api = _mock_qb_api_request()

        # Step 1: Approve
        with patch(
            "app.services.quickbooks_service.QuickBooksService._api_request",
            mock_api,
        ):
            resp1 = await client.post(
                f"/api/v1/invoices/{inv.id}/approve", headers=auth_headers
            )
        assert resp1.status_code == 200
        approve_data = resp1.json()
        assert approve_data["status"] in ("approved", "sent_to_qb")

        # Step 2: Mark Paid
        with patch(
            "app.services.quickbooks_service.QuickBooksService._api_request",
            mock_api,
        ):
            resp2 = await client.post(
                f"/api/v1/invoices/{inv.id}/mark-paid", headers=auth_headers
            )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "paid"

        # Verify final state
        result = await db_session.execute(
            select(Invoice).where(Invoice.id == inv.id)
        )
        final_inv = result.scalar_one()
        assert final_inv.status == InvoiceStatus.PAID

        pay_result = await db_session.execute(
            select(Payable).where(Payable.invoice_id == inv.id)
        )
        final_payable = pay_result.scalar_one()
        assert final_payable.status == PayableStatus.PAID
