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
        assert data["real_available"] == 7000.0
