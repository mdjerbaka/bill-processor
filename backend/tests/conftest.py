"""Shared test fixtures for the bill-processor test suite.

Uses an async SQLite in-memory database so tests run fast and don't
need any external services.
"""

from __future__ import annotations

import os
import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ── Set required env vars BEFORE any app imports ────────────────
_test_fernet_key = Fernet.generate_key().decode()
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("ENCRYPTION_KEY", _test_fernet_key)
os.environ.setdefault("APP_URL", "http://localhost:5173")

from app.core.database import Base, get_db  # noqa: E402
from app.core.security import hash_password, create_access_token  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import User  # noqa: E402


# ── Engine & session factory for every test ────────────────────

@pytest_asyncio.fixture()
async def db_engine():
    """Create a fresh in-memory SQLite engine per test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional DB session that rolls back after each test."""
    factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False,
    )
    async with factory() as session:
        yield session


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client with the DB dependency overridden."""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Convenience fixtures ───────────────────────────────────────

@pytest_asyncio.fixture()
async def test_user(db_session: AsyncSession) -> User:
    """Create and return a test user in the DB."""
    user = User(
        username="testuser",
        hashed_password=hash_password("testpass123"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture()
async def auth_headers(test_user: User) -> dict[str, str]:
    """Return Authorization headers with a valid JWT for test_user."""
    token = create_access_token({"sub": test_user.username})
    return {"Authorization": f"Bearer {token}"}
