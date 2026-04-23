"""BuilderTrend auto-forward helper.

Forwards approved invoices to a BuilderTrend receipts inbox via the user's
connected Microsoft 365 account, and tracks the last forward outcome so the
user can see status in Settings.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AppSetting, Attachment, Payable
from app.services.microsoft_graph_service import MicrosoftGraphService

logger = logging.getLogger(__name__)

# AppSetting keys for BT forward status
STATUS_KEY = "buildertrend_last_status"
STATUS_AT_KEY = "buildertrend_last_status_at"
STATUS_DETAIL_KEY = "buildertrend_last_status_detail"

# MS Graph attachment limit (base64 expansion ~33%, keep under 4MB final payload)
MAX_ATTACHMENT_BYTES = 3_500_000


async def _set_status(
    db: AsyncSession, user_id: int, status: str, detail: str = ""
) -> None:
    """Persist last BT forward status for visibility in the UI."""
    now_iso = datetime.now(timezone.utc).isoformat()
    for key, value in (
        (STATUS_KEY, status),
        (STATUS_AT_KEY, now_iso),
        (STATUS_DETAIL_KEY, detail[:500]),
    ):
        result = await db.execute(
            select(AppSetting).where(
                AppSetting.key == key, AppSetting.user_id == user_id
            )
        )
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            db.add(AppSetting(key=key, value=value, user_id=user_id))
    await db.flush()


async def _load_attachment_bytes(
    db: AsyncSession, attachment_id: Optional[int]
) -> tuple[Optional[bytes], Optional[str], Optional[str]]:
    """Return (bytes, filename, content_type) for an attachment, or all None."""
    if not attachment_id:
        return None, None, None
    result = await db.execute(
        select(Attachment).where(Attachment.id == attachment_id)
    )
    att = result.scalar_one_or_none()
    if not att or not att.file_path:
        return None, None, None
    p = Path(att.file_path)
    if not p.is_file():
        return None, att.filename, att.content_type
    try:
        data = p.read_bytes()
    except Exception as e:
        logger.warning(f"BT forward: failed to read attachment {att.file_path}: {e}")
        return None, att.filename, att.content_type
    # Prefer the stored MIME type; fall back to guessing from filename.
    content_type = att.content_type or (
        mimetypes.guess_type(att.filename or "")[0] or "application/octet-stream"
    )
    return data, att.filename, content_type


async def forward_invoice_to_buildertrend(
    db: AsyncSession,
    user_id: int,
    payable: Payable,
    attachment_id: Optional[int],
) -> bool:
    """Forward an approved invoice to BuilderTrend if configured.

    Best-effort: never raises. Records last status to AppSettings for UI display.
    Returns True only if the email was successfully sent.
    """
    try:
        # Load BT config
        cfg_result = await db.execute(
            select(AppSetting).where(
                AppSetting.key.in_(
                    ["buildertrend_forward_email", "buildertrend_forward_enabled"]
                ),
                AppSetting.user_id == user_id,
            )
        )
        cfg = {row.key: row.value for row in cfg_result.scalars().all()}
        bt_email = (cfg.get("buildertrend_forward_email") or "").strip()
        bt_enabled = cfg.get("buildertrend_forward_enabled") == "true"

        if not bt_enabled:
            return False
        if not bt_email:
            await _set_status(
                db, user_id, "error", "Auto-forward enabled but no BuilderTrend email configured."
            )
            logger.warning("BT forward: enabled but no email address set")
            return False

        ms_svc = MicrosoftGraphService(db, user_id)
        if not await ms_svc._get_valid_token():
            await _set_status(
                db,
                user_id,
                "error",
                "Microsoft 365 not connected. Connect Microsoft in Settings to enable forwarding.",
            )
            logger.warning("BT forward: MS Graph not connected for user %s", user_id)
            return False

        # Build subject and body
        vendor = payable.vendor_name or "Unknown"
        inv_num = payable.invoice_number or "N/A"
        amount = payable.amount or 0.0
        subject = f"Invoice: {vendor} - {inv_num}"
        body_html = (
            f"<p>Approved invoice forwarded from Bill Processor.</p>"
            f"<p><strong>Vendor:</strong> {vendor}<br>"
            f"<strong>Invoice #:</strong> {inv_num}<br>"
            f"<strong>Amount:</strong> ${amount:,.2f}</p>"
        )

        # Attachment (best-effort)
        bt_attachments = []
        attachment_warning = ""
        file_bytes, filename, content_type = await _load_attachment_bytes(db, attachment_id)
        if file_bytes is not None:
            if len(file_bytes) <= MAX_ATTACHMENT_BYTES:
                bt_attachments.append(
                    {
                        "name": filename or "invoice.pdf",
                        "contentType": content_type or "application/octet-stream",
                        "contentBytes": base64.b64encode(file_bytes).decode(),
                    }
                )
            else:
                attachment_warning = (
                    f" Attachment '{filename}' was too large ({len(file_bytes)} bytes) "
                    "and was not included."
                )
                logger.warning(
                    "BT forward: attachment too large (%s bytes), sending email without it",
                    len(file_bytes),
                )
        elif attachment_id:
            attachment_warning = " Attachment file was missing on disk and was not included."

        sent = await ms_svc.send_mail(
            subject=subject,
            body_html=body_html,
            to_email=bt_email,
            attachments=bt_attachments or None,
        )

        if sent:
            detail = f"Forwarded '{subject}' to {bt_email}." + attachment_warning
            await _set_status(db, user_id, "ok", detail)
            logger.info("BT forward: %s", detail)
            return True

        await _set_status(
            db,
            user_id,
            "error",
            f"Microsoft Graph rejected the send to {bt_email}. Check the email address and that your Microsoft account can send mail.",
        )
        return False

    except Exception as e:  # noqa: BLE001
        logger.exception("BT forward: unexpected failure")
        try:
            await _set_status(db, user_id, "error", f"Unexpected error: {e}")
        except Exception:
            pass
        return False
