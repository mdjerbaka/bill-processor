"""QuickBooks endpoint tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch, AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_value
from app.models.models import Invoice, InvoiceStatus, QBOToken


async def _create_qbo_token(db: AsyncSession) -> QBOToken:
    now = datetime.now(timezone.utc)
    token = QBOToken(
        access_token=encrypt_value("test-access-token"),
        refresh_token=encrypt_value("test-refresh-token"),
        realm_id="1234567890",
        expires_at=now + timedelta(hours=1),
        refresh_expires_at=now + timedelta(days=100),
    )
    db.add(token)
    await db.flush()
    return token


class TestQBOConnect:

    async def test_connect_no_client_id(self, client: AsyncClient, auth_headers):
        """Should 400 if QBO_CLIENT_ID is not configured."""
        resp = await client.get("/api/v1/quickbooks/connect", headers=auth_headers)
        assert resp.status_code == 400
        assert "client id" in resp.json()["detail"].lower()

    @patch("app.api.quickbooks.settings")
    async def test_connect_returns_auth_url(self, mock_settings, client, auth_headers):
        mock_settings.qbo_client_id = "test-client-id"
        mock_settings.qbo_client_secret = "test-secret"
        mock_settings.qbo_redirect_uri = "http://localhost:8000/api/v1/quickbooks/callback"
        mock_settings.qbo_environment = "sandbox"
        mock_settings.app_url = "http://localhost:5173"

        resp = await client.get("/api/v1/quickbooks/connect", headers=auth_headers)
        assert resp.status_code == 200
        assert "auth_url" in resp.json()
        assert "appcenter.intuit.com" in resp.json()["auth_url"]


class TestQBOStatus:

    async def test_status_not_connected(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/quickbooks/status", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["connected"] is False

    async def test_status_connected(
        self, client: AsyncClient, auth_headers, db_session
    ):
        await _create_qbo_token(db_session)
        await db_session.commit()
        resp = await client.get("/api/v1/quickbooks/status", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["connected"] is True


class TestQBOSendBill:

    async def test_send_bill_invoice_not_found(
        self, client: AsyncClient, auth_headers
    ):
        resp = await client.post(
            "/api/v1/quickbooks/send-bill/9999",
            params={"qbo_vendor_id": "123", "qbo_account_id": "456"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_send_bill_not_approved(
        self, client: AsyncClient, auth_headers, db_session
    ):
        inv = Invoice(
            vendor_name="Test",
            total_amount=100,
            status=InvoiceStatus.EXTRACTED,
            user_id=1,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(inv)
        await db_session.commit()
        resp = await client.post(
            f"/api/v1/quickbooks/send-bill/{inv.id}",
            params={"qbo_vendor_id": "123", "qbo_account_id": "456"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
