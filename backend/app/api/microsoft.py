"""Microsoft 365 OAuth and Graph API routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.api.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db, async_session_factory
from app.models.models import AppSetting, User
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

    svc = MicrosoftGraphService(db, user.id)
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
        return HTMLResponse(
            content=f"<html><body><h2>Microsoft 365 connection failed.</h2><p>{error_description or error}</p><p>You can close this tab and try again.</p><script>window.close()</script></body></html>"
        )

    async with async_session_factory() as db:
        svc = MicrosoftGraphService(db)
        success = await svc.exchange_code(code)

        if not success:
            return HTMLResponse(
                content="<html><body><h2>Microsoft 365 connection failed.</h2><p>Token exchange failed. You can close this tab and try again.</p><script>window.close()</script></body></html>"
            )

        await db.commit()
        return HTMLResponse(
            content="<html><body><h2>Microsoft 365 connected successfully!</h2><p>You can close this tab.</p><script>window.close()</script></body></html>"
        )


@router.get("/status")
async def ms_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Check Microsoft 365 connection status."""
    svc = MicrosoftGraphService(db, user.id)
    info = await svc.get_connection_info()
    return info


@router.post("/test")
async def ms_test(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Test the Microsoft 365 Graph API connection."""
    svc = MicrosoftGraphService(db, user.id)
    connected, message = await svc.test_connection()
    return {"connected": connected, "message": message}


@router.post("/disconnect")
async def ms_disconnect(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Remove Microsoft 365 connection tokens."""
    svc = MicrosoftGraphService(db, user.id)
    await svc.disconnect()
    return {"disconnected": True}


@router.get("/folders")
async def ms_list_folders(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List available mail folders from the connected Microsoft 365 account."""
    svc = MicrosoftGraphService(db, user.id)
    folders = await svc.list_mail_folders()
    return {"folders": folders}


@router.get("/folder-setting")
async def ms_get_folder_setting(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the currently configured mail folder for polling."""
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == "ms_mail_folder_id")
    )
    folder_id_setting = result.scalar_one_or_none()
    result2 = await db.execute(
        select(AppSetting).where(AppSetting.key == "ms_mail_folder_name")
    )
    folder_name_setting = result2.scalar_one_or_none()
    return {
        "folder_id": folder_id_setting.value if folder_id_setting else "",
        "folder_name": folder_name_setting.value if folder_name_setting else "All Folders",
    }


@router.post("/folder-setting")
async def ms_save_folder_setting(
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Save the mail folder to poll."""
    folder_id = body.get("folder_id", "")
    folder_name = body.get("folder_name", "All Folders")

    for key, value in [("ms_mail_folder_id", folder_id), ("ms_mail_folder_name", folder_name)]:
        result = await db.execute(select(AppSetting).where(AppSetting.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            db.add(AppSetting(key=key, value=value))

    await db.commit()
    return {"saved": True, "folder_id": folder_id, "folder_name": folder_name}


@router.post("/poll")
async def ms_poll_now(
    user: User = Depends(get_current_user),
):
    """Manually trigger email polling from Microsoft 365 + OCR."""
    async with async_session_factory() as db:
        svc = MicrosoftGraphService(db, user.id)
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
