"""Payables endpoint tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    AppSetting,
    Invoice,
    InvoiceStatus,
    Payable,
    PayableStatus,
)


async def _create_payable(
    db: AsyncSession,
    vendor: str = "Test Vendor",
    amount: float = 500.0,
    status: PayableStatus = PayableStatus.OUTSTANDING,
    overdue: bool = False,
    user_id: int = 1,
    included_in_cashflow: bool = True,
) -> tuple[Invoice, Payable]:
    inv = Invoice(
        vendor_name=vendor,
        invoice_number="INV-P01",
        total_amount=amount,
        status=InvoiceStatus.APPROVED,
        user_id=user_id,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(inv)
    await db.flush()

    due = datetime.now(timezone.utc) - timedelta(days=5) if overdue else datetime.now(timezone.utc) + timedelta(days=30)
    payable = Payable(
        invoice_id=inv.id,
        vendor_name=vendor,
        amount=amount,
        due_date=due,
        status=status,
        user_id=user_id,
        included_in_cashflow=included_in_cashflow,
    )
    db.add(payable)
    await db.flush()
    return inv, payable


class TestPayablesList:

    async def test_list_empty(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/payables", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_with_data(
        self, client: AsyncClient, auth_headers, db_session
    ):
        await _create_payable(db_session, vendor="Vendor A")
        await _create_payable(db_session, vendor="Vendor B", amount=300.0)
        await db_session.commit()
        resp = await client.get("/api/v1/payables", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["total_outstanding"] == 800.0

    async def test_list_excludes_paid_by_default(
        self, client: AsyncClient, auth_headers, db_session
    ):
        await _create_payable(db_session, vendor="Unpaid")
        await _create_payable(db_session, vendor="Paid", status=PayableStatus.PAID)
        await db_session.commit()
        resp = await client.get("/api/v1/payables", headers=auth_headers)
        assert resp.json()["total"] == 1

    async def test_list_include_paid(
        self, client: AsyncClient, auth_headers, db_session
    ):
        await _create_payable(db_session, vendor="Unpaid")
        await _create_payable(db_session, vendor="Paid", status=PayableStatus.PAID)
        await db_session.commit()
        resp = await client.get(
            "/api/v1/payables", params={"include_paid": True}, headers=auth_headers
        )
        assert resp.json()["total"] == 2


class TestBankBalance:

    async def test_set_and_get_balance(
        self, client: AsyncClient, auth_headers, db_session
    ):
        resp = await client.post(
            "/api/v1/payables/bank-balance",
            json={"bank_balance": 10000.0},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["bank_balance"] == 10000.0
        assert data["buffer"] == 0.0
        assert data["real_available"] == 10000.0  # no outstanding

    async def test_real_balance_subtracts_outstanding(
        self, client: AsyncClient, auth_headers, db_session
    ):
        await _create_payable(db_session, amount=3000.0)
        setting = AppSetting(key="bank_balance", value="10000.0", user_id=1)
        db_session.add(setting)
        await db_session.commit()

        resp = await client.get("/api/v1/payables/real-balance", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["bank_balance"] == 10000.0
        assert data["total_outstanding"] == 3000.0
        assert data["total_included_payables"] == 3000.0
        assert data["real_available"] == 7000.0

    async def test_excluded_payable_not_subtracted(
        self, client: AsyncClient, auth_headers, db_session
    ):
        """Payables with included_in_cashflow=False should NOT reduce real balance."""
        await _create_payable(db_session, amount=3000.0, included_in_cashflow=True)
        await _create_payable(db_session, vendor="Excluded Vendor", amount=2000.0, included_in_cashflow=False)
        setting = AppSetting(key="bank_balance", value="10000.0", user_id=1)
        db_session.add(setting)
        await db_session.commit()

        resp = await client.get("/api/v1/payables/real-balance", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["bank_balance"] == 10000.0
        assert data["total_outstanding"] == 5000.0  # all payables
        assert data["total_included_payables"] == 3000.0  # only toggled-on
        assert data["real_available"] == 7000.0  # 10000 - 3000 (excluded not subtracted)


class TestBuffer:

    async def test_set_buffer(
        self, client: AsyncClient, auth_headers, db_session
    ):
        # Set bank balance first
        await client.post(
            "/api/v1/payables/bank-balance",
            json={"bank_balance": 50000.0},
            headers=auth_headers,
        )
        resp = await client.post(
            "/api/v1/payables/buffer",
            json={"buffer": 20000.0},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["buffer"] == 20000.0
        assert data["real_available"] == 30000.0

    async def test_buffer_subtracts_from_real_available(
        self, client: AsyncClient, auth_headers, db_session
    ):
        await _create_payable(db_session, amount=5000.0)
        setting = AppSetting(key="bank_balance", value="50000.0", user_id=1)
        buf_setting = AppSetting(key="balance_buffer", value="20000.0", user_id=1)
        db_session.add(setting)
        db_session.add(buf_setting)
        await db_session.commit()

        resp = await client.get("/api/v1/payables/real-balance", headers=auth_headers)
        data = resp.json()
        assert data["bank_balance"] == 50000.0
        assert data["total_outstanding"] == 5000.0
        assert data["total_included_payables"] == 5000.0
        assert data["buffer"] == 20000.0
        assert data["real_available"] == 25000.0


class TestPermanentPayable:

    async def test_create_permanent_payable(
        self, client: AsyncClient, auth_headers
    ):
        resp = await client.post(
            "/api/v1/payables",
            json={
                "vendor_name": "Weekly Payroll",
                "amount": 12206.0,
                "is_permanent": True,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_permanent"] is True
        assert data["vendor_name"] == "Weekly Payroll"

    async def test_cannot_mark_permanent_as_paid(
        self, client: AsyncClient, auth_headers, db_session
    ):
        _, payable = await _create_payable(db_session, vendor="Payroll")
        payable.is_permanent = True
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/payables/{payable.id}/mark-paid",
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "Permanent" in resp.json()["detail"]

    async def test_list_includes_is_permanent(
        self, client: AsyncClient, auth_headers, db_session
    ):
        _, payable = await _create_payable(db_session, vendor="Payroll")
        payable.is_permanent = True
        await db_session.commit()

        resp = await client.get("/api/v1/payables", headers=auth_headers)
        items = resp.json()["items"]
        assert any(p["is_permanent"] for p in items)
