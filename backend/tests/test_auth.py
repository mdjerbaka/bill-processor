"""Auth endpoint tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.models import User


# ── Setup ────────────────────────────────────────────────────────

class TestSetup:
    """POST /api/v1/auth/setup"""

    async def test_initial_setup_creates_user(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/setup", json={
            "username": "admin",
            "password": "securepass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_setup_rejects_duplicate(self, client: AsyncClient, test_user):
        """Setup should fail if a user already exists."""
        resp = await client.post("/api/v1/auth/setup", json={
            "username": "another",
            "password": "password123",
        })
        assert resp.status_code == 400
        assert "already completed" in resp.json()["detail"].lower()

    async def test_setup_rejects_short_password(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/setup", json={
            "username": "admin",
            "password": "short",
        })
        assert resp.status_code == 422

    async def test_setup_rejects_short_username(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/setup", json={
            "username": "ab",
            "password": "password123",
        })
        assert resp.status_code == 422


# ── Login ────────────────────────────────────────────────────────

class TestLogin:
    """POST /api/v1/auth/login"""

    async def test_login_valid_credentials(self, client: AsyncClient, test_user):
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "testpass123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_login_wrong_password(self, client: AsyncClient, test_user):
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "testuser", "password": "wrongpass"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            data={"username": "nobody", "password": "whatever"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 401


# ── Token / Protected Routes ─────────────────────────────────────

class TestAuth:
    """Token validation & protected endpoints."""

    async def test_protected_route_without_token(self, client: AsyncClient):
        resp = await client.get("/api/v1/invoices")
        assert resp.status_code == 401

    async def test_protected_route_with_invalid_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/invoices",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401

    async def test_protected_route_with_valid_token(
        self, client: AsyncClient, auth_headers
    ):
        resp = await client.get("/api/v1/invoices", headers=auth_headers)
        assert resp.status_code == 200


# ── Setup Status ─────────────────────────────────────────────────

class TestSetupStatus:
    """GET /api/v1/auth/setup-status"""

    async def test_setup_status_no_user(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/setup-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_user"] is False
        assert data["is_setup_complete"] is False

    async def test_setup_status_with_user(self, client: AsyncClient, test_user):
        resp = await client.get("/api/v1/auth/setup-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_user"] is True
