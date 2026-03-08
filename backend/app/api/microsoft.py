"""Microsoft 365 OAuth and Graph API routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db, async_session_factory
from app.models.models import User
from app.services.microsoft_graph_service import MicrosoftGraphService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/microsoft", tags=["microsoft"])


@router.get("/connect")
async def ms_connect(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the Microsoft OAuth2 authorization URL."""
    if not settings.ms_client_id:
        raise HTTPException(
            status_code=400,
            detail="Microsoft 365 not configured. Set MS_CLIENT_ID and MS_CLIENT_SECRET in .env",
        )

    svc = MicrosoftGraphService(db)
    auth_url = svc.get_auth_url()
    return {"auth_url": auth_url}


@router.get("/callback")
async def ms_callback(
    code: str = Query(...),
    state: str = Query("ms_connect"),
    error: str = Query(None),
    error_description: str = Query(None),
):
    """Microsoft OAuth2 callback — exchanges code for tokens."""
    if error:
        logger.error(f"MS OAuth error: {error} — {error_description}")
        return RedirectResponse(
            url=f"{settings.app_url}/settings?ms_error={error_description or error}"
        )

    async with async_session_factory() as db:
        svc = MicrosoftGraphService(db)
        success = await svc.exchange_code(code)

        if not success:
            return RedirectResponse(
                url=f"{settings.app_url}/settings?ms_error=token_exchange_failed"
            )

        await db.commit()
        return RedirectResponse(
            url=f"{settings.app_url}/settings?ms_connected=true"
        )


@router.get("/status")
async def ms_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Check Microsoft 365 connection status."""
    svc = MicrosoftGraphService(db)
    info = await svc.get_connection_info()
    return info


@router.post("/test")
async def ms_test(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Test the Microsoft 365 Graph API connection."""
    svc = MicrosoftGraphService(db)
    connected, message = await svc.test_connection()
    return {"connected": connected, "message": message}


@router.post("/disconnect")
async def ms_disconnect(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Remove Microsoft 365 connection tokens."""
    svc = MicrosoftGraphService(db)
    await svc.disconnect()
    return {"disconnected": True}


@router.post("/poll")
async def ms_poll_now(
    user: User = Depends(get_current_user),
):
    """Manually trigger email polling from Microsoft 365 + OCR."""
    async with async_session_factory() as db:
        svc = MicrosoftGraphService(db)
        new_ids = await svc.poll_inbox()

        # Process each email through OCR (same as IMAP flow)
        from app.api.settings import _process_email

        processed = 0
        errors = []

        for email_id in new_ids:
            try:
                await _process_email(db, email_id)
                processed += 1
            except Exception as e:
                logger.error(f"Processing MS email {email_id} failed: {e}")
                errors.append(str(e)[:120])

        return {
            "emails_fetched": len(new_ids),
            "invoices_created": processed,
            "errors": errors,
        }
