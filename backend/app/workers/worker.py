"""ARQ background worker — handles email polling and OCR extraction."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

# Configure logging BEFORE anything else — ARQ doesn't go through main.py
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.models.models import (
    Attachment,
    Email,
    EmailStatus,
    Invoice,
    InvoiceLineItem,
    InvoiceStatus,
    User,
)
from app.services.email_service import EmailService
from app.services.job_matching_service import JobMatchingService
from app.services.ocr_service import get_ocr_provider_async
from app.services.quickbooks_service import QuickBooksService
from app.services.payables_service import PayablesService
from app.services.recurring_bills_service import RecurringBillsService
from app.services.notification_service import NotificationService
from app.services.microsoft_graph_service import MicrosoftGraphService

from sqlalchemy import select, func

logger = logging.getLogger(__name__)
settings = get_settings()

# Simple lock to prevent overlapping polls
_poll_lock = asyncio.Lock()


async def _try_match_recurring_bill(db, invoice, user_id):
    """Try to auto-match an invoice to a recurring bill occurrence."""
    try:
        bills_svc = RecurringBillsService(db, user_id)
        matched = await bills_svc.auto_match_invoice(invoice)
        if matched:
            logger.info(f"Invoice {invoice.id} auto-matched to bill occurrence {matched.id}")
    except Exception as e:
        logger.error(f"Recurring bill auto-match failed for invoice {invoice.id}: {e}")


async def poll_email_inbox(ctx: dict) -> dict:
    """Task: Poll email inboxes (IMAP + Microsoft Graph) for new invoice emails."""
    if _poll_lock.locked():
        logger.debug("Poll already in progress, skipping this cycle")
        return {"skipped": True}

    async with _poll_lock:
        async with async_session_factory() as db:
            all_new_ids = []

            # Get all users
            users_result = await db.execute(select(User))
            users = users_result.scalars().all()

            for u in users:
                # 1) IMAP polling (Gmail / generic IMAP)
                try:
                    svc = EmailService(db, u.id)
                    imap_ids = await svc.poll_inbox()
                    all_new_ids.extend(imap_ids)
                except Exception as e:
                    logger.warning(f"IMAP poll failed for user {u.id} (may not be configured): {e}")

                # 2) Microsoft Graph polling (Outlook / Microsoft 365)
                try:
                    graph_svc = MicrosoftGraphService(db, u.id)
                    if await graph_svc.is_connected():
                        graph_ids = await graph_svc.poll_inbox()
                        all_new_ids.extend(graph_ids)
                        if graph_ids:
                            logger.info(f"MS Graph poll fetched {len(graph_ids)} new emails for user {u.id}")
                except Exception as e:
                    logger.warning(f"MS Graph poll failed for user {u.id}: {e}")

            # Trigger extraction for each new email
            for email_id in all_new_ids:
                await process_email_attachments(ctx, email_id)

            # Store last poll time
            from app.models.models import AppSetting
            result = await db.execute(
                select(AppSetting).where(AppSetting.key == "last_email_poll")
            )
            setting = result.scalar_one_or_none()
            now_str = datetime.now(timezone.utc).isoformat()
            if setting:
                setting.value = now_str
            else:
                db.add(AppSetting(key="last_email_poll", value=now_str))

            await db.commit()

    return {"new_emails": len(all_new_ids)}


async def process_email_attachments(ctx: dict, email_id: int) -> dict:
    """Task: Run OCR extraction on all attachments of an email."""
    async with async_session_factory() as db:
        # Get email with attachments
        result = await db.execute(
            select(Email).where(Email.id == email_id)
        )
        email_record = result.scalar_one_or_none()
        if not email_record:
            return {"error": "Email not found"}

        email_user_id = email_record.user_id

        # Skip if already processed (dedup guard against overlapping polls)
        if email_record.status in (EmailStatus.PROCESSING, EmailStatus.EXTRACTED):
            logger.debug(f"Email {email_id} already processed/processing, skipping")
            return {"skipped": True}

        email_record.status = EmailStatus.PROCESSING

        # Get attachments
        result = await db.execute(
            select(Attachment).where(Attachment.email_id == email_id)
        )
        attachments = result.scalars().all()

        if not attachments:
            # No attachments — try extracting from email body text
            if email_record.body_text and len(email_record.body_text.strip()) > 50:
                logger.info(f"Email {email_id} has no attachments, trying body text extraction")
                try:
                    ocr = await get_ocr_provider_async()
                    if hasattr(ocr, 'extract_from_text'):
                        extracted = await ocr.extract_from_text(email_record.body_text)

                        has_data = extracted.vendor_name or extracted.invoice_number or extracted.total_amount
                        if extracted.confidence_score >= 0.15 and has_data:
                            # Invoice-level dedup
                            from sqlalchemy import and_
                            is_dup = False
                            if extracted.vendor_name and extracted.invoice_number and extracted.total_amount:
                                dup_check = await db.execute(
                                    select(func.count(Invoice.id)).where(
                                        and_(
                                            func.lower(Invoice.vendor_name) == extracted.vendor_name.strip().lower(),
                                            Invoice.invoice_number == str(extracted.invoice_number).strip(),
                                            Invoice.total_amount == extracted.total_amount,
                                        )
                                    )
                                )
                                is_dup = dup_check.scalar() > 0

                            if not is_dup:
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
                                    user_id=email_user_id,
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

                                matcher = JobMatchingService(db, email_user_id)
                                await matcher.match_invoice(invoice)

                                # Create payable + auto-send to QuickBooks if auto-matched
                                if invoice.status == InvoiceStatus.AUTO_MATCHED:
                                    try:
                                        payables_svc = PayablesService(db, email_user_id)
                                        await payables_svc.create_payable(invoice)
                                        await db.flush()
                                        logger.info(f"Created payable for auto-matched invoice {invoice.id}")
                                    except Exception as pay_err:
                                        logger.error(f"Payable creation failed for invoice {invoice.id}: {pay_err}")
                                    try:
                                        qb_svc = QuickBooksService(db, email_user_id)
                                        bill_id, vendor_id = await qb_svc.auto_send_bill(invoice)
                                        if bill_id:
                                            invoice.qbo_bill_id = bill_id
                                            invoice.qbo_vendor_id = vendor_id
                                            invoice.status = InvoiceStatus.SENT_TO_QB
                                            await db.flush()
                                            logger.info(f"Auto-sent invoice {invoice.id} to QB as bill {bill_id}")
                                    except Exception as qb_err:
                                        logger.error(f"QB auto-send failed for invoice {invoice.id}: {qb_err}")

                                logger.info(
                                    f"Extracted invoice {invoice.id} from email body: "
                                    f"vendor={extracted.vendor_name}, total={extracted.total_amount}"
                                )
                                await _try_match_recurring_bill(db, invoice, email_user_id)
                                email_record.status = EmailStatus.EXTRACTED
                                await db.commit()
                                return {"invoices_created": 1, "source": "body_text"}
                            else:
                                logger.info(f"Duplicate body invoice skipped: {extracted.vendor_name}")
                        else:
                            logger.info(f"Email {email_id} body text is not an invoice")
                except Exception as e:
                    logger.error(f"Body text extraction failed for email {email_id}: {e}")

            email_record.status = EmailStatus.FAILED
            email_record.error_message = "No supported attachments found"
            await db.commit()
            return {"error": "No attachments"}

        ocr = await get_ocr_provider_async()
        invoices_created = 0

        for att in attachments:
            try:
                # Skip if an invoice already exists for this attachment (dedup guard)
                existing_invoice = await db.execute(
                    select(func.count(Invoice.id)).where(Invoice.attachment_id == att.id)
                )
                if existing_invoice.scalar() > 0:
                    logger.debug(f"Invoice already exists for attachment {att.id}, skipping")
                    continue

                # Run OCR extraction
                extracted = await ocr.extract(att.file_path)

                # Skip non-invoice attachments (e.g. spreadsheets with no bill data)
                has_data = extracted.vendor_name or extracted.invoice_number or extracted.total_amount
                if extracted.confidence_score < 0.15 and not has_data:
                    logger.info(
                        f"Skipping attachment {att.filename}: no invoice data detected "
                        f"(confidence={extracted.confidence_score:.2f})"
                    )
                    continue

                # Invoice-level dedup: skip if same vendor + invoice# + amount already exists
                if extracted.vendor_name and extracted.invoice_number and extracted.total_amount:
                    from sqlalchemy import and_
                    dup_check = await db.execute(
                        select(func.count(Invoice.id)).where(
                            and_(
                                func.lower(Invoice.vendor_name) == extracted.vendor_name.strip().lower(),
                                Invoice.invoice_number == str(extracted.invoice_number).strip(),
                                Invoice.total_amount == extracted.total_amount,
                            )
                        )
                    )
                    if dup_check.scalar() > 0:
                        logger.info(
                            f"Duplicate invoice skipped: {extracted.vendor_name} "
                            f"#{extracted.invoice_number} ${extracted.total_amount}"
                        )
                        continue

                # Create invoice record
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
                    user_id=email_user_id,
                )

                # Parse dates
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

                # Set status based on confidence
                if extracted.confidence_score < 0.8:
                    invoice.status = InvoiceStatus.NEEDS_REVIEW

                db.add(invoice)
                await db.flush()

                # Add line items
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

                # Run job matching
                matcher = JobMatchingService(db, email_user_id)
                await matcher.match_invoice(invoice)

                # Create payable + auto-send to QuickBooks if auto-matched
                if invoice.status == InvoiceStatus.AUTO_MATCHED:
                    try:
                        payables_svc = PayablesService(db, email_user_id)
                        await payables_svc.create_payable(invoice)
                        await db.flush()
                        logger.info(f"Created payable for auto-matched invoice {invoice.id}")
                    except Exception as pay_err:
                        logger.error(f"Payable creation failed for invoice {invoice.id}: {pay_err}")
                    try:
                        qb_svc = QuickBooksService(db, email_user_id)
                        bill_id, vendor_id = await qb_svc.auto_send_bill(invoice)
                        if bill_id:
                            invoice.qbo_bill_id = bill_id
                            invoice.qbo_vendor_id = vendor_id
                            invoice.status = InvoiceStatus.SENT_TO_QB
                            await db.flush()
                            logger.info(f"Auto-sent invoice {invoice.id} to QB as bill {bill_id}")
                    except Exception as qb_err:
                        logger.error(f"QB auto-send failed for invoice {invoice.id}: {qb_err}")

                invoices_created += 1
                logger.info(
                    f"Extracted invoice {invoice.id} from attachment {att.filename}: "
                    f"vendor={extracted.vendor_name}, total={extracted.total_amount}, "
                    f"confidence={extracted.confidence_score:.2f}"
                )
                await _try_match_recurring_bill(db, invoice, email_user_id)

            except Exception as e:
                logger.error(f"OCR extraction failed for attachment {att.id}: {e}")
                # Create a placeholder invoice for manual entry
                invoice = Invoice(
                    email_id=email_id,
                    attachment_id=att.id,
                    status=InvoiceStatus.NEEDS_REVIEW,
                    error_message=str(e),
                    user_id=email_user_id,
                )
                db.add(invoice)

        # If no invoices from attachments and email has body text, try body extraction
        if invoices_created == 0 and email_record.body_text and len(email_record.body_text.strip()) > 50:
            try:
                if hasattr(ocr, 'extract_from_text'):
                    logger.info(f"No invoices from attachments for email {email_id}, trying body text")
                    extracted = await ocr.extract_from_text(email_record.body_text)

                    has_data = extracted.vendor_name or extracted.invoice_number or extracted.total_amount
                    if extracted.confidence_score >= 0.15 and has_data:
                        from sqlalchemy import and_
                        is_dup = False
                        if extracted.vendor_name and extracted.invoice_number and extracted.total_amount:
                            dup_check = await db.execute(
                                select(func.count(Invoice.id)).where(
                                    and_(
                                        func.lower(Invoice.vendor_name) == extracted.vendor_name.strip().lower(),
                                        Invoice.invoice_number == str(extracted.invoice_number).strip(),
                                        Invoice.total_amount == extracted.total_amount,
                                    )
                                )
                            )
                            is_dup = dup_check.scalar() > 0

                        if not is_dup:
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
                                user_id=email_user_id,
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

                            matcher = JobMatchingService(db, email_user_id)
                            await matcher.match_invoice(invoice)

                            # Create payable + auto-send to QuickBooks if auto-matched
                            if invoice.status == InvoiceStatus.AUTO_MATCHED:
                                try:
                                    payables_svc = PayablesService(db, email_user_id)
                                    await payables_svc.create_payable(invoice)
                                    await db.flush()
                                    logger.info(f"Created payable for auto-matched invoice {invoice.id}")
                                except Exception as pay_err:
                                    logger.error(f"Payable creation failed for invoice {invoice.id}: {pay_err}")
                                try:
                                    qb_svc = QuickBooksService(db, email_user_id)
                                    bill_id, vendor_id = await qb_svc.auto_send_bill(invoice)
                                    if bill_id:
                                        invoice.qbo_bill_id = bill_id
                                        invoice.qbo_vendor_id = vendor_id
                                        invoice.status = InvoiceStatus.SENT_TO_QB
                                        await db.flush()
                                        logger.info(f"Auto-sent invoice {invoice.id} to QB as bill {bill_id}")
                                except Exception as qb_err:
                                    logger.error(f"QB auto-send failed for invoice {invoice.id}: {qb_err}")

                            invoices_created += 1
                            logger.info(
                                f"Extracted invoice {invoice.id} from email body (fallback): "
                                f"vendor={extracted.vendor_name}, total={extracted.total_amount}"
                            )
                            await _try_match_recurring_bill(db, invoice, email_user_id)
            except Exception as e:
                logger.error(f"Body text fallback extraction failed for email {email_id}: {e}")

        email_record.status = EmailStatus.EXTRACTED
        await db.commit()

    return {"invoices_created": invoices_created}


async def generate_bill_occurrences(ctx: dict) -> dict:
    """Cron: Generate upcoming bill occurrences and update statuses."""
    async with async_session_factory() as db:
        users_result = await db.execute(select(User))
        users = users_result.scalars().all()

        total_created = 0
        total_overdue = 0
        total_due_soon = 0
        total_notifs = 0

        for u in users:
            svc = RecurringBillsService(db, u.id)

            # Generate occurrences for the next 60 days
            created = await svc.generate_occurrences(days_ahead=60)

            # Update overdue and due-soon statuses
            overdue_count = await svc.check_overdue()
            due_soon_count = await svc.check_due_soon()

            # Generate notifications for due-soon and overdue bills
            notif_svc = NotificationService(db, u.id)
            due_notifs = await notif_svc.generate_due_soon_notifications()
            overdue_notifs = await notif_svc.generate_overdue_notifications()
            credit_danger_notifs = await notif_svc.generate_credit_danger_notifications()

            total_created += created
            total_overdue += overdue_count
            total_due_soon += due_soon_count
            total_notifs += due_notifs + overdue_notifs + credit_danger_notifs

        await db.commit()

    logger.info(
        f"Bill occurrences: {total_created} created, {total_overdue} overdue, "
        f"{total_due_soon} due soon, {total_notifs} notifications"
    )
    return {
        "occurrences_created": total_created,
        "overdue": total_overdue,
        "due_soon": total_due_soon,
        "notifications": total_notifs,
    }


async def send_daily_digest(ctx: dict) -> dict:
    """Cron: Send daily email digest of upcoming and overdue bills."""
    async with async_session_factory() as db:
        users_result = await db.execute(select(User))
        users = users_result.scalars().all()
        sent_count = 0

        for u in users:
            notif_svc = NotificationService(db, u.id)
            graph_svc = MicrosoftGraphService(db, u.id)

            # Check if MS Graph is connected for this user
            connected = await graph_svc.is_connected()
            if not connected:
                continue

            # Build digest HTML
            html = await notif_svc.build_daily_digest_html()
            if not html:
                continue

            # Send email
            sent = await graph_svc.send_mail(
                subject="Bill Processor — Daily Digest",
                body_html=html,
            )
            if sent:
                sent_count += 1

        await db.commit()

    if sent_count == 0:
        return {"skipped": True, "reason": "No digests to send"}
    return {"sent": sent_count}


class WorkerSettings:
    """ARQ worker configuration."""

    functions = [poll_email_inbox, process_email_attachments, generate_bill_occurrences, send_daily_digest]

    cron_jobs = [
        cron(
            poll_email_inbox,
            second={0, 30},
            run_at_startup=True,
        ),
        cron(
            generate_bill_occurrences,
            minute={0},
            run_at_startup=True,
        ),
        cron(
            send_daily_digest,
            hour={12},
            minute={0},
        ),
    ]

    redis_settings = RedisSettings.from_dsn(settings.redis_url)

    # Retry failed tasks
    max_tries = 2
    job_timeout = 600  # 10 minutes
