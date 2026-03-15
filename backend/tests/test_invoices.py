"""Invoice endpoint tests."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Email,
    EmailStatus,
    Invoice,
    InvoiceLineItem,
    InvoiceStatus,
    Job,
    JobSource,
    Payable,
    PayableStatus,
)


# ── Helpers ──────────────────────────────────────────────────────

async def _create_invoice(
    db: AsyncSession,
    vendor_name: str = "Test Vendor",
    total: float = 1000.0,
    status: InvoiceStatus = InvoiceStatus.EXTRACTED,
    with_line_items: bool = False,
    job_id: int | None = None,
) -> Invoice:
    inv = Invoice(
        vendor_name=vendor_name,
        invoice_number="INV-001",
        total_amount=total,
        subtotal=total,
        status=status,
        job_id=job_id,
        confidence_score=0.95,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(inv)
    await db.flush()

    if with_line_items:
        li = InvoiceLineItem(
            invoice_id=inv.id,
            description="Widget A",
            quantity=2,
            unit_price=500.0,
            amount=1000.0,
        )
        db.add(li)
        await db.flush()

    return inv


async def _create_job(db: AsyncSession, name: str = "Job Alpha") -> Job:
    job = Job(name=name, code="J-001", source=JobSource.MANUAL, is_active=True)
    db.add(job)
    await db.flush()
    return job


# ── List ─────────────────────────────────────────────────────────

class TestInvoiceList:

    async def test_list_empty(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/invoices", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_with_data(
        self, client: AsyncClient, auth_headers, db_session
    ):
        await _create_invoice(db_session)
        await db_session.commit()
        resp = await client.get("/api/v1/invoices", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["vendor_name"] == "Test Vendor"

    async def test_list_filter_by_status(
        self, client: AsyncClient, auth_headers, db_session
    ):
        await _create_invoice(db_session, status=InvoiceStatus.EXTRACTED)
        await _create_invoice(db_session, vendor_name="Other", status=InvoiceStatus.APPROVED)
        await db_session.commit()
        resp = await client.get(
            "/api/v1/invoices", params={"status": "extracted"}, headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_list_filter_by_vendor(
        self, client: AsyncClient, auth_headers, db_session
    ):
        await _create_invoice(db_session, vendor_name="Acme Corp")
        await _create_invoice(db_session, vendor_name="Other LLC")
        await db_session.commit()
        resp = await client.get(
            "/api/v1/invoices", params={"vendor": "Acme"}, headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_list_pagination(
        self, client: AsyncClient, auth_headers, db_session
    ):
        for i in range(5):
            await _create_invoice(db_session, vendor_name=f"Vendor {i}")
        await db_session.commit()
        resp = await client.get(
            "/api/v1/invoices", params={"page": 1, "page_size": 2}, headers=auth_headers
        )
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2


# ── Get Single ───────────────────────────────────────────────────

class TestInvoiceGet:

    async def test_get_by_id(
        self, client: AsyncClient, auth_headers, db_session
    ):
        inv = await _create_invoice(db_session, with_line_items=True)
        await db_session.commit()
        resp = await client.get(f"/api/v1/invoices/{inv.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == inv.id
        assert len(data["line_items"]) == 1

    async def test_get_not_found(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/invoices/9999", headers=auth_headers)
        assert resp.status_code == 404


# ── Update ───────────────────────────────────────────────────────

class TestInvoiceUpdate:

    async def test_update_fields(
        self, client: AsyncClient, auth_headers, db_session
    ):
        inv = await _create_invoice(db_session)
        await db_session.commit()
        resp = await client.put(
            f"/api/v1/invoices/{inv.id}",
            json={"vendor_name": "Updated Vendor", "total_amount": 2000.0},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["vendor_name"] == "Updated Vendor"
        assert resp.json()["total_amount"] == 2000.0

    async def test_update_not_found(self, client: AsyncClient, auth_headers):
        resp = await client.put(
            "/api/v1/invoices/9999",
            json={"vendor_name": "X"},
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ── Approve ──────────────────────────────────────────────────────

class TestInvoiceApprove:

    async def test_approve_creates_payable(
        self, client: AsyncClient, auth_headers, db_session
    ):
        inv = await _create_invoice(db_session, status=InvoiceStatus.EXTRACTED)
        await db_session.commit()
        resp = await client.post(
            f"/api/v1/invoices/{inv.id}/approve", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    async def test_approve_already_approved(
        self, client: AsyncClient, auth_headers, db_session
    ):
        inv = await _create_invoice(db_session, status=InvoiceStatus.APPROVED)
        await db_session.commit()
        resp = await client.post(
            f"/api/v1/invoices/{inv.id}/approve", headers=auth_headers
        )
        assert resp.status_code == 400
