"""Health endpoint and edge-case tests."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest
from httpx import AsyncClient


class TestHealthEndpoint:

    async def test_health_returns_all_fields(self, client: AsyncClient):
        """Health endpoint should be publicly accessible (no auth)."""
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "version" in data
        assert "uptime_seconds" in data
        assert "db_connected" in data
        assert "redis_connected" in data

    async def test_health_db_connected(self, client: AsyncClient):
        resp = await client.get("/api/v1/health")
        data = resp.json()
        # Health check uses the module-level engine (not overridden),
        # so in test it may or may not connect. Just verify key exists.
        assert isinstance(data["db_connected"], bool)

    async def test_health_redis_status(self, client: AsyncClient):
        """Redis may or may not be running in test env."""
        resp = await client.get("/api/v1/health")
        data = resp.json()
        # Just ensure the key exists; value depends on test environment
        assert "redis_connected" in data


class TestAttachmentEndpoint:

    async def test_attachment_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/attachments/1")
        assert resp.status_code == 401

    async def test_attachment_not_found(
        self, client: AsyncClient, auth_headers
    ):
        resp = await client.get("/api/v1/attachments/9999", headers=auth_headers)
        assert resp.status_code == 404
