"""Settings management routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db, async_session_factory
from app.core.config import get_settings
from app.core.security import encrypt_value, decrypt_value
from app.models.models import (
    AppSetting,
    Attachment,
    Email,
    EmailStatus,
    Invoice,
    InvoiceLineItem,
    InvoiceStatus,
    Job,
    Payable,
    User,
    VendorJobMapping,
)
from app.schemas.schemas import (
    EmailConfigRequest,
    EmailConfigResponse,
    OCRConfigRequest,
    OCRConfigResponse,
)
from app.services.email_service import EmailService
from app.services.job_matching_service import JobMatchingService
from app.services.ocr_service import get_ocr_provider_async

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/email", response_model=EmailConfigResponse)
async def get_email_config(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get current email configuration (password masked)."""
    svc = EmailService(db)
    try:
        config = await svc.get_email_config()
    except (ValueError, Exception):
        # Encryption key changed — credentials are unreadable
        return EmailConfigResponse(
            imap_host="",
            imap_port=993,
            imap_username="",
            use_ssl=True,
            is_connected=False,
        )

    if not config:
        return EmailConfigResponse(
            imap_host="",
            imap_port=993,
            imap_username="",
            use_ssl=True,
            is_connected=False,
        )

    # Test connection
    connected, _ = await svc.test_connection()

    return EmailConfigResponse(
        imap_host=config["imap_host"],
        imap_port=int(config["imap_port"]),
        imap_username=config["imap_username"],
        use_ssl=config["imap_use_ssl"] == "true",
        is_connected=connected,
    )


@router.post("/email", response_model=EmailConfigResponse)
async def save_email_config(
    req: EmailConfigRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Save email (IMAP) configuration."""
    settings_to_save = {
        "imap_host": (req.imap_host, False),
        "imap_port": (str(req.imap_port), False),
        "imap_username": (req.imap_username, False),
        "imap_password": (req.imap_password, True),  # encrypt
        "imap_use_ssl": ("true" if req.use_ssl else "false", False),
    }

    for key, (value, should_encrypt) in settings_to_save.items():
        result = await db.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        setting = result.scalar_one_or_none()

        stored_value = encrypt_value(value) if should_encrypt else value

        if setting:
            setting.value = stored_value
            setting.is_encrypted = should_encrypt
        else:
            setting = AppSetting(
                key=key,
                value=stored_value,
                is_encrypted=should_encrypt,
            )
            db.add(setting)

    await db.flush()

    # Test connection
    svc = EmailService(db)
    connected, message = await svc.test_connection()

    return EmailConfigResponse(
        imap_host=req.imap_host,
        imap_port=req.imap_port,
        imap_username=req.imap_username,
        use_ssl=req.use_ssl,
        is_connected=connected,
    )


@router.post("/email/test")
async def test_email_connection(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Test the stored email connection."""
    svc = EmailService(db)
    connected, message = await svc.test_connection()
    return {"connected": connected, "message": message}


@router.post("/email/poll")
async def poll_email_now(
    user: User = Depends(get_current_user),
):
    """Manually trigger email polling + OCR processing (no worker needed)."""
    async with async_session_factory() as db:
        svc = EmailService(db)
        new_ids = await svc.poll_inbox()

        processed = 0
        errors = []

        for email_id in new_ids:
            try:
                await _process_email(db, email_id)
                processed += 1
            except Exception as e:
                logger.error(f"Processing email {email_id} failed: {e}")
                errors.append(str(e)[:120])

        return {
            "emails_fetched": len(new_ids),
            "invoices_created": processed,
            "errors": errors,
        }


@router.post("/email/process-pending")
async def process_pending_emails(
    user: User = Depends(get_current_user),
):
    """Process any emails that were polled but still in PENDING status."""
    async with async_session_factory() as db:
        result = await db.execute(
            select(Email).where(Email.status == EmailStatus.PENDING)
        )
        pending_emails = result.scalars().all()

        processed = 0
        skipped = 0
        errors = []

        for email_record in pending_emails:
            try:
                await _process_email(db, email_record.id)
                processed += 1
            except Exception as e:
                logger.error(f"Processing email {email_record.id} failed: {e}")
                errors.append(f"Email {email_record.id}: {str(e)[:100]}")

        return {
            "total_pending": len(pending_emails),
            "processed": processed,
            "errors": errors,
        }


async def _process_email(db: AsyncSession, email_id: int):
    """Run OCR extraction on attachments of a single email (inline, no worker)."""
    result = await db.execute(select(Email).where(Email.id == email_id))
    email_record = result.scalar_one_or_none()
    if not email_record:
        return

    email_record.status = EmailStatus.PROCESSING

    result = await db.execute(
        select(Attachment).where(Attachment.email_id == email_id)
    )
    attachments = result.scalars().all()

    ocr = await get_ocr_provider_async()

    if not attachments:
        # No attachments — try extracting from email body text
        if email_record.body_text and len(email_record.body_text.strip()) > 50:
            try:
                if hasattr(ocr, 'extract_from_text'):
                    extracted = await ocr.extract_from_text(email_record.body_text)
                    has_data = extracted.vendor_name or extracted.invoice_number or extracted.total_amount
                    if extracted.confidence_score >= 0.15 and has_data:
                        invoice = Invoice(
                            email_id=email_id,
                            attachment_id=None,
                            vendor_name=extracted.vendor_name,
                            vendor_address=extracted.vendor_address,
                            invoice_number=extracted.invoice_number,
                            total_amount=extracted.total_amount,
                            subtotal=extracted.subtotal,
                            tax_amount=extracted.tax_amount,
                            extracted_data=extracted.to_dict(),
                            confidence_score=extracted.confidence_score,
                            status=InvoiceStatus.NEEDS_REVIEW,
                        )
                        if extracted.invoice_date:
                            try:
                                from dateutil.parser import parse as parse_date
                                invoice.invoice_date = parse_date(extracted.invoice_date)
                            except (ValueError, TypeError):
                                pass
                        if extracted.due_date:
                            try:
                                from dateutil.parser import parse as parse_date
                                invoice.due_date = parse_date(extracted.due_date)
                            except (ValueError, TypeError):
                                pass
                        if extracted.confidence_score < 0.8:
                            invoice.status = InvoiceStatus.NEEDS_REVIEW
                        db.add(invoice)
                        await db.flush()
                        for item_data in extracted.line_items:
                            li = InvoiceLineItem(
                                invoice_id=invoice.id,
                                description=item_data.get("description"),
                                quantity=item_data.get("quantity"),
                                unit_price=item_data.get("unit_price"),
                                amount=item_data.get("amount"),
                                product_code=item_data.get("product_code"),
                            )
                            db.add(li)
                        await db.flush()
                        matcher = JobMatchingService(db)
                        await matcher.match_invoice(invoice)
                        logger.info(f"Extracted invoice {invoice.id} from email body text")
            except Exception as e:
                logger.error(f"Body text extraction failed for email {email_id}: {e}")

        email_record.status = EmailStatus.EXTRACTED
        await db.commit()
        return

    for att in attachments:
        try:
            extracted = await ocr.extract(att.file_path)

            invoice = Invoice(
                email_id=email_id,
                attachment_id=att.id,
                vendor_name=extracted.vendor_name,
                vendor_address=extracted.vendor_address,
                invoice_number=extracted.invoice_number,
                total_amount=extracted.total_amount,
                subtotal=extracted.subtotal,
                tax_amount=extracted.tax_amount,
                extracted_data=extracted.to_dict(),
                confidence_score=extracted.confidence_score,
                status=InvoiceStatus.EXTRACTED,
            )

            if extracted.invoice_date:
                try:
                    from dateutil.parser import parse as parse_date
                    invoice.invoice_date = parse_date(extracted.invoice_date)
                except (ValueError, TypeError):
                    pass
            if extracted.due_date:
                try:
                    from dateutil.parser import parse as parse_date
                    invoice.due_date = parse_date(extracted.due_date)
                except (ValueError, TypeError):
                    pass

            if extracted.confidence_score < 0.8:
                invoice.status = InvoiceStatus.NEEDS_REVIEW

            db.add(invoice)
            await db.flush()

            for item_data in extracted.line_items:
                li = InvoiceLineItem(
                    invoice_id=invoice.id,
                    description=item_data.get("description"),
                    quantity=item_data.get("quantity"),
                    unit_price=item_data.get("unit_price"),
                    amount=item_data.get("amount"),
                    product_code=item_data.get("product_code"),
                )
                db.add(li)

            await db.flush()

            matcher = JobMatchingService(db)
            await matcher.match_invoice(invoice)

            logger.info(
                f"Extracted invoice {invoice.id} from attachment {att.filename}: "
                f"vendor={extracted.vendor_name}, total={extracted.total_amount}"
            )

        except Exception as e:
            logger.error(f"OCR failed for attachment {att.id}: {e}")
            invoice = Invoice(
                email_id=email_id,
                attachment_id=att.id,
                status=InvoiceStatus.NEEDS_REVIEW,
                error_message=str(e),
            )
            db.add(invoice)

    email_record.status = EmailStatus.EXTRACTED
    await db.commit()


# ── OCR / API Key settings ───────────────────────────────

OCR_SETTING_KEYS = {
    "ocr_provider": False,
    "openai_api_key": True,
    "azure_endpoint": False,
    "azure_api_key": True,
    "aws_access_key_id": True,
    "aws_secret_access_key": True,
    "aws_region": False,
}


@router.get("/ocr", response_model=OCRConfigResponse)
async def get_ocr_config(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get current OCR / API key configuration (keys masked)."""
    values = {}
    for key in OCR_SETTING_KEYS:
        result = await db.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        setting = result.scalar_one_or_none()
        if setting:
            if setting.is_encrypted:
                try:
                    values[key] = decrypt_value(setting.value)
                except (ValueError, Exception):
                    # Key was encrypted with old key — remove the corrupt entry
                    await db.delete(setting)
                    await db.flush()
            else:
                values[key] = setting.value

    # Fall back to .env for OpenAI key status
    if "openai_api_key" not in values and settings.openai_api_key:
        values["openai_api_key"] = settings.openai_api_key

    return OCRConfigResponse(
        ocr_provider=values.get("ocr_provider", "none"),
        openai_key_set=bool(values.get("openai_api_key")),
        azure_endpoint=values.get("azure_endpoint"),
        azure_key_set=bool(values.get("azure_api_key")),
        aws_key_set=bool(values.get("aws_access_key_id")),
        aws_region=values.get("aws_region"),
    )


@router.post("/ocr", response_model=OCRConfigResponse)
async def save_ocr_config(
    req: OCRConfigRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Save OCR provider and API keys."""
    fields = {
        "ocr_provider": (req.ocr_provider, False),
    }
    # Only save keys that are provided (non-empty)
    if req.openai_api_key:
        fields["openai_api_key"] = (req.openai_api_key, True)
    if req.azure_endpoint:
        fields["azure_endpoint"] = (req.azure_endpoint, False)
    if req.azure_api_key:
        fields["azure_api_key"] = (req.azure_api_key, True)
    if req.aws_access_key_id:
        fields["aws_access_key_id"] = (req.aws_access_key_id, True)
    if req.aws_secret_access_key:
        fields["aws_secret_access_key"] = (req.aws_secret_access_key, True)
    if req.aws_region:
        fields["aws_region"] = (req.aws_region, False)

    for key, (value, should_encrypt) in fields.items():
        result = await db.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        setting = result.scalar_one_or_none()
        stored_value = encrypt_value(value) if should_encrypt else value

        if setting:
            setting.value = stored_value
            setting.is_encrypted = should_encrypt
        else:
            setting = AppSetting(
                key=key,
                value=stored_value,
                is_encrypted=should_encrypt,
            )
            db.add(setting)

    await db.flush()

    # Re-read to build response
    return await get_ocr_config(db=db, user=user)


@router.post("/ocr/test")
async def test_ocr_config(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Test whether the configured OCR API key is valid."""
    # Read provider from DB
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == "ocr_provider")
    )
    setting = result.scalar_one_or_none()
    provider = setting.value if setting else "none"

    if provider == "none":
        return {"ok": False, "message": "No OCR provider configured"}

    if provider == "openai":
        result = await db.execute(
            select(AppSetting).where(AppSetting.key == "openai_api_key")
        )
        key_setting = result.scalar_one_or_none()
        if not key_setting:
            return {"ok": False, "message": "OpenAI API key not set"}
        api_key = decrypt_value(key_setting.value) if key_setting.is_encrypted else key_setting.value
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key)
            await client.models.list()
            return {"ok": True, "message": "OpenAI API key is valid"}
        except Exception as e:
            return {"ok": False, "message": str(e)[:200]}

    return {"ok": True, "message": f"Provider '{provider}' configured (key validation not implemented)"}


# ── QuickBooks credential settings ─────────────────────

QB_SETTING_KEYS = {
    "qbo_client_id": False,
    "qbo_client_secret": True,
    "qbo_redirect_uri": False,
    "qbo_environment": False,
}


@router.get("/quickbooks")
async def get_qb_config(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get QuickBooks credential configuration (secrets masked)."""
    values = {}
    for key in QB_SETTING_KEYS:
        result = await db.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        setting = result.scalar_one_or_none()
        if setting:
            if setting.is_encrypted:
                try:
                    values[key] = decrypt_value(setting.value)
                except (ValueError, Exception):
                    values[key] = ""
            else:
                values[key] = setting.value

    # Fall back to .env values
    if not values.get("qbo_client_id"):
        values["qbo_client_id"] = settings.qbo_client_id or ""
    if not values.get("qbo_client_secret"):
        values["qbo_client_secret"] = settings.qbo_client_secret or ""
    if not values.get("qbo_redirect_uri"):
        values["qbo_redirect_uri"] = settings.qbo_redirect_uri or "http://localhost:8000/api/v1/quickbooks/callback"
    if not values.get("qbo_environment"):
        values["qbo_environment"] = settings.qbo_environment or "sandbox"

    return {
        "client_id": values.get("qbo_client_id", ""),
        "client_secret_set": bool(values.get("qbo_client_secret")),
        "redirect_uri": values.get("qbo_redirect_uri", ""),
        "environment": values.get("qbo_environment", "sandbox"),
    }


@router.post("/quickbooks")
async def save_qb_config(
    req: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Save QuickBooks credential configuration."""
    fields = {}
    if req.get("client_id") is not None:
        fields["qbo_client_id"] = (req["client_id"], False)
    if req.get("client_secret"):
        fields["qbo_client_secret"] = (req["client_secret"], True)
    if req.get("redirect_uri"):
        fields["qbo_redirect_uri"] = (req["redirect_uri"], False)
    if req.get("environment"):
        fields["qbo_environment"] = (req["environment"], False)

    for key, (value, should_encrypt) in fields.items():
        result = await db.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        setting = result.scalar_one_or_none()
        stored_value = encrypt_value(value) if should_encrypt else value

        if setting:
            setting.value = stored_value
            setting.is_encrypted = should_encrypt
        else:
            setting = AppSetting(
                key=key,
                value=stored_value,
                is_encrypted=should_encrypt,
            )
            db.add(setting)

    await db.flush()
    return await get_qb_config(db=db, user=user)


@router.delete("/reset-invoices")
async def reset_invoice_data(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete ALL invoice-related data so the email poller re-processes everything.

    Deletes in FK order: payables → line_items → invoices → attachments → emails.
    Also clears the last_email_poll timestamp so the poller re-scans the inbox.
    """
    from sqlalchemy import delete as sa_delete

    # Count before deleting
    inv_count = (await db.execute(select(func.count(Invoice.id)))).scalar() or 0
    email_count = (await db.execute(select(func.count(Email.id)))).scalar() or 0

    # Delete in FK dependency order
    await db.execute(sa_delete(Payable))
    await db.execute(sa_delete(InvoiceLineItem))
    await db.execute(sa_delete(Invoice))
    await db.execute(sa_delete(Attachment))
    await db.execute(sa_delete(Email))

    # Clear last poll time so the poller re-fetches recent messages
    await db.execute(
        sa_delete(AppSetting).where(AppSetting.key == "last_email_poll")
    )

    await db.flush()
    logger.info(f"Reset invoice data: {inv_count} invoices, {email_count} emails deleted")
    return {
        "deleted_invoices": inv_count,
        "deleted_emails": email_count,
        "message": "All invoice data cleared. Email poller will re-process on next run.",
    }


@router.delete("/reset-jobs")
async def reset_job_data(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete ALL job data (jobs and vendor-job mappings)."""
    from sqlalchemy import delete as sa_delete

    job_count = (await db.execute(select(func.count(Job.id)))).scalar() or 0

    await db.execute(sa_delete(VendorJobMapping))
    await db.execute(sa_delete(Job))
    await db.flush()

    logger.info(f"Reset job data: {job_count} jobs deleted")
    return {
        "deleted_jobs": job_count,
        "message": "All job data cleared.",
    }
