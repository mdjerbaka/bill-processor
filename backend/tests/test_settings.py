"""Settings endpoint tests."""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_value, decrypt_value
from app.models.models import AppSetting


class TestEmailSettings:

    async def test_get_default_empty(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/settings/email", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["imap_host"] == ""

    async def test_save_email_config(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/settings/email",
            json={
                "imap_host": "imap.gmail.com",
                "imap_port": 993,
                "imap_username": "test@gmail.com",
                "imap_password": "app-password-here",
                "use_ssl": True,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imap_host"] == "imap.gmail.com"
        assert data["imap_username"] == "test@gmail.com"

    async def test_read_back_masks_password(
        self, client: AsyncClient, auth_headers, db_session
    ):
        """Save email config, then GET — password should not be returned."""
        # Save first
        await client.post(
            "/api/v1/settings/email",
            json={
                "imap_host": "imap.test.com",
                "imap_port": 993,
                "imap_username": "user@test.com",
                "imap_password": "secret123",
                "use_ssl": True,
            },
            headers=auth_headers,
        )
        # Read back
        resp = await client.get("/api/v1/settings/email", headers=auth_headers)
        data = resp.json()
        # Password should not be in the response
        assert "imap_password" not in data or data.get("imap_password") is None

    async def test_email_test_connection(self, client: AsyncClient, auth_headers):
        """Test connection endpoint (will fail without real IMAP, but should not 500)."""
        resp = await client.post("/api/v1/settings/email/test", headers=auth_headers)
        # Might be 200 with connected=false since no config saved
        assert resp.status_code == 200


class TestOCRSettings:

    async def test_get_default(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/settings/ocr", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ocr_provider"] in ("none", "openai")
        assert data["openai_key_set"] is False

    async def test_save_openai_key(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/settings/ocr",
            json={"ocr_provider": "openai", "openai_api_key": "sk-test-123"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ocr_provider"] == "openai"
        assert data["openai_key_set"] is True

    async def test_save_preserves_existing_key_when_blank(
        self, client: AsyncClient, auth_headers
    ):
        """Saving with blank key should not overwrite existing key."""
        # Save a key first
        await client.post(
            "/api/v1/settings/ocr",
            json={"ocr_provider": "openai", "openai_api_key": "sk-real-key"},
            headers=auth_headers,
        )
        # Save again with blank key
        await client.post(
            "/api/v1/settings/ocr",
            json={"ocr_provider": "openai"},
            headers=auth_headers,
        )
        # Key should still be set
        resp = await client.get("/api/v1/settings/ocr", headers=auth_headers)
        assert resp.json()["openai_key_set"] is True

    async def test_save_azure_config(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/settings/ocr",
            json={
                "ocr_provider": "azure",
                "azure_endpoint": "https://my-resource.cognitiveservices.azure.com",
                "azure_api_key": "az-key-123",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ocr_provider"] == "azure"
        assert data["azure_key_set"] is True
        assert data["azure_endpoint"] == "https://my-resource.cognitiveservices.azure.com"

    async def test_save_aws_config(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/settings/ocr",
            json={
                "ocr_provider": "aws",
                "aws_access_key_id": "AKIA123",
                "aws_secret_access_key": "secret",
                "aws_region": "us-west-2",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ocr_provider"] == "aws"
        assert data["aws_key_set"] is True
        assert data["aws_region"] == "us-west-2"

    async def test_ocr_test_no_provider(
        self, client: AsyncClient, auth_headers, db_session
    ):
        """Test endpoint when no provider configured."""
        resp = await client.post("/api/v1/settings/ocr/test", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False

    async def test_ocr_test_openai_no_key(
        self, client: AsyncClient, auth_headers, db_session
    ):
        """Set provider to openai but don't save a key."""
        setting = AppSetting(key="ocr_provider", value="openai")
        db_session.add(setting)
        await db_session.commit()
        resp = await client.post("/api/v1/settings/ocr/test", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["ok"] is False


class TestEncryption:

    def test_encrypt_decrypt_roundtrip(self):
        original = "my-secret-api-key"
        encrypted = encrypt_value(original)
        assert encrypted != original
        assert decrypt_value(encrypted) == original

    def test_different_encryptions_same_value(self):
        """Two encryptions of the same value should produce different ciphertext."""
        v1 = encrypt_value("hello")
        v2 = encrypt_value("hello")
        assert v1 != v2  # Fernet uses random IV
