"""FastAPI application entrypoint."""

from __future__ import annotations

import time
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import init_db, get_db, async_session_factory
from app.api import auth, invoices, jobs, payables, settings as settings_router, quickbooks, junk, microsoft, recurring_bills, notifications, receivables, payments_out, vendor_accounts
from app.api.auth import get_current_user
from app.models.models import AppSetting, User

logger = logging.getLogger(__name__)
app_settings = get_settings()

APP_VERSION = "0.1.0"
START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & shutdown events."""
    # Startup: validate critical config
    logging.basicConfig(level=logging.INFO)
    if not app_settings.database_url:
        raise RuntimeError("DATABASE_URL is not set. Add it to your .env file.")
    if not app_settings.secret_key:
        raise RuntimeError("SECRET_KEY is not set. Add it to your .env file.")
    if not app_settings.encryption_key:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"  "
            "and add it to your .env file."
        )
    logger.info("Starting Bill Processor API v%s", APP_VERSION)
    await init_db()
    yield
    # Shutdown
    logger.info("Shutting down Bill Processor API")


app = FastAPI(
    title="Bill Processor API",
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[app_settings.app_url, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount API routes ─────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1")
app.include_router(invoices.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(payables.router, prefix="/api/v1")
app.include_router(settings_router.router, prefix="/api/v1")
app.include_router(quickbooks.router, prefix="/api/v1")
app.include_router(microsoft.router, prefix="/api/v1")
app.include_router(junk.router, prefix="/api/v1")
app.include_router(recurring_bills.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(receivables.router, prefix="/api/v1")
app.include_router(payments_out.router, prefix="/api/v1")
app.include_router(vendor_accounts.router, prefix="/api/v1")


# ── Health check ─────────────────────────────────────────
@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint for monitoring."""
    uptime = time.time() - START_TIME

    # Check DB
    db_ok = False
    last_poll = None
    ocr_provider = None
    try:
        async with async_session_factory() as db:
            await db.execute(select(AppSetting).limit(1))
            db_ok = True

            # Get last email poll time
            result = await db.execute(
                select(AppSetting).where(AppSetting.key == "last_email_poll")
            )
            setting = result.scalar_one_or_none()
            if setting:
                last_poll = setting.value

            # Get OCR provider from DB first, fall back to .env
            result = await db.execute(
                select(AppSetting).where(AppSetting.key == "ocr_provider")
            )
            ocr_setting = result.scalar_one_or_none()
            ocr_provider = ocr_setting.value if ocr_setting else app_settings.ocr_provider
            if ocr_provider == "none":
                ocr_provider = None
    except Exception:
        pass

    # Check Redis
    redis_ok = False
    try:
        import redis as redis_lib
        r = redis_lib.from_url(app_settings.redis_url)
        r.ping()
        redis_ok = True
    except Exception:
        pass

    return {
        "status": "healthy" if db_ok and redis_ok else "degraded",
        "version": APP_VERSION,
        "uptime_seconds": round(uptime, 1),
        "last_email_poll": last_poll,
        "db_connected": db_ok,
        "redis_connected": redis_ok,
        "ocr_provider": ocr_provider,
    }


# ── Attachment file serving ──────────────────────────────
@app.get("/api/v1/attachments/{attachment_id}")
async def serve_attachment(
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Serve an attachment file (for the bill review side-by-side view)."""
    from app.models.models import Attachment

    result = await db.execute(
        select(Attachment).where(Attachment.id == attachment_id)
    )
    att = result.scalar_one_or_none()
    if not att:
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    return FileResponse(
        att.file_path,
        media_type=att.content_type,
        filename=att.filename,
    )
