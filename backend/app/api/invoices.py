"""Invoice / bill management routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.models import (
    Attachment,
    Invoice,
    InvoiceLineItem,
    InvoiceStatus,
    Job,
    Payable,
    PayableStatus,
    User,
)
from app.schemas.schemas import (
    InvoiceCreateRequest,
    InvoiceListResponse,
    InvoiceSchema,
    InvoiceUpdateRequest,
    JobMatchSuggestion,
)
from app.services.job_matching_service import JobMatchingService
from app.services.payables_service import PayablesService
from app.services.quickbooks_service import QuickBooksService

logger = __import__('logging').getLogger(__name__)

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _invoice_to_schema(inv: Invoice) -> InvoiceSchema:
    return InvoiceSchema(
        id=inv.id,
        email_id=inv.email_id,
        attachment_id=inv.attachment_id,
        vendor_name=inv.vendor_name,
        vendor_address=inv.vendor_address,
        invoice_number=inv.invoice_number,
        invoice_date=inv.invoice_date,
        due_date=inv.due_date,
        total_amount=inv.total_amount,
        subtotal=inv.subtotal,
        tax_amount=inv.tax_amount,
        confidence_score=inv.confidence_score,
        job_id=inv.job_id,
        job_name=inv.job.name if inv.job else None,
        match_method=inv.match_method,
        status=inv.status.value,
        qbo_bill_id=inv.qbo_bill_id,
        qbo_payment_id=inv.qbo_payment_id,
        error_message=inv.error_message,
        notes=inv.notes,
        line_items=[
            {
                "id": li.id,
                "description": li.description,
                "quantity": li.quantity,
                "unit_price": li.unit_price,
                "amount": li.amount,
                "product_code": li.product_code,
            }
            for li in (inv.line_items or [])
        ],
        created_at=inv.created_at,
        updated_at=inv.updated_at,
    )


@router.post("", response_model=InvoiceSchema)
async def create_invoice(
    req: InvoiceCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Manually create an invoice (not from email/OCR)."""
    invoice = Invoice(
        vendor_name=req.vendor_name,
        invoice_number=req.invoice_number,
        invoice_date=req.invoice_date,
        due_date=req.due_date,
        total_amount=req.total_amount,
        subtotal=req.subtotal,
        tax_amount=req.tax_amount,
        job_id=req.job_id,
        notes=req.notes,
        status=InvoiceStatus.NEEDS_REVIEW,
        match_method="manual",
        user_id=user.id,
    )
    db.add(invoice)
    await db.flush()

    # Add line items if provided
    if req.line_items:
        for item_data in req.line_items:
            li = InvoiceLineItem(
                invoice_id=invoice.id,
                description=item_data.description,
                quantity=item_data.quantity,
                unit_price=item_data.unit_price,
                amount=item_data.amount,
                product_code=item_data.product_code,
            )
            db.add(li)
        await db.flush()

    # Re-fetch with relationships
    result = await db.execute(
        select(Invoice)
        .options(joinedload(Invoice.job), joinedload(Invoice.line_items))
        .where(Invoice.id == invoice.id)
    )
    invoice = result.unique().scalar_one_or_none()
    return _invoice_to_schema(invoice)


@router.get("", response_model=InvoiceListResponse)
async def list_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    vendor: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all invoices with pagination and optional filters."""
    query = select(Invoice).options(
        joinedload(Invoice.job),
        joinedload(Invoice.line_items),
    ).where(Invoice.is_junked == False, Invoice.user_id == user.id)

    if status:
        try:
            status_enum = InvoiceStatus(status)
            query = query.where(Invoice.status == status_enum)
        except ValueError:
            pass

    if vendor:
        query = query.where(Invoice.vendor_name.ilike(f"%{vendor}%"))

    # Count
    count_query = select(func.count(Invoice.id)).where(Invoice.is_junked == False, Invoice.user_id == user.id)
    if status:
        try:
            count_query = count_query.where(Invoice.status == InvoiceStatus(status))
        except ValueError:
            pass
    if vendor:
        count_query = count_query.where(Invoice.vendor_name.ilike(f"%{vendor}%"))

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Paginate
    query = query.order_by(Invoice.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    invoices = result.unique().scalars().all()

    return InvoiceListResponse(
        items=[_invoice_to_schema(inv) for inv in invoices],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{invoice_id}", response_model=InvoiceSchema)
async def get_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single invoice by ID."""
    result = await db.execute(
        select(Invoice)
        .options(joinedload(Invoice.job), joinedload(Invoice.line_items))
        .where(Invoice.id == invoice_id, Invoice.user_id == user.id)
    )
    invoice = result.unique().scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _invoice_to_schema(invoice)


@router.put("/{invoice_id}", response_model=InvoiceSchema)
async def update_invoice(
    invoice_id: int,
    req: InvoiceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update invoice fields (manual corrections to extracted data)."""
    result = await db.execute(
        select(Invoice)
        .options(joinedload(Invoice.job), joinedload(Invoice.line_items))
        .where(Invoice.id == invoice_id, Invoice.user_id == user.id)
    )
    invoice = result.unique().scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Update fields
    update_data = req.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "line_items" and value is not None:
            # Replace line items
            for li in invoice.line_items:
                await db.delete(li)
            await db.flush()
            for item_data in value:
                li = InvoiceLineItem(
                    invoice_id=invoice.id,
                    description=item_data.get("description"),
                    quantity=item_data.get("quantity"),
                    unit_price=item_data.get("unit_price"),
                    amount=item_data.get("amount"),
                    product_code=item_data.get("product_code"),
                )
                db.add(li)
        elif field == "job_id" and value is not None:
            invoice.job_id = value
            invoice.match_method = "manual"
            # Learn from manual assignment
            matcher = JobMatchingService(db, user.id)
            await matcher.learn_from_assignment(invoice.vendor_name, value)
        else:
            setattr(invoice, field, value)

    invoice.updated_at = datetime.now(timezone.utc)
    await db.flush()

    # Re-fetch with relationships
    result = await db.execute(
        select(Invoice)
        .options(joinedload(Invoice.job), joinedload(Invoice.line_items))
        .where(Invoice.id == invoice_id, Invoice.user_id == user.id)
    )
    invoice = result.unique().scalar_one_or_none()
    return _invoice_to_schema(invoice)


@router.post("/{invoice_id}/approve")
async def approve_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Approve an invoice, create a payable entry, then permanently delete the invoice."""
    result = await db.execute(
        select(Invoice)
        .options(joinedload(Invoice.job), joinedload(Invoice.line_items))
        .where(Invoice.id == invoice_id, Invoice.user_id == user.id)
    )
    invoice = result.unique().scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status in (InvoiceStatus.APPROVED, InvoiceStatus.SENT_TO_QB, InvoiceStatus.PAID):
        raise HTTPException(status_code=400, detail="Invoice already approved")

    invoice.status = InvoiceStatus.APPROVED

    # Create or restore payable entry
    existing_payable_result = await db.execute(
        select(Payable).where(Payable.invoice_id == invoice_id)
    )
    existing_payable = existing_payable_result.scalar_one_or_none()
    if existing_payable:
        # Payable already exists (was junked) – restore it
        existing_payable.is_junked = False
        existing_payable.junked_at = None
        existing_payable.status = PayableStatus.OUTSTANDING
        existing_payable.paid_at = None
        # Update amount/due in case invoice was edited
        existing_payable.vendor_name = invoice.vendor_name or "Unknown"
        existing_payable.amount = invoice.total_amount or 0.0
        existing_payable.due_date = invoice.due_date
        existing_payable.invoice_number = invoice.invoice_number
        existing_payable.job_name = invoice.job.name if invoice.job else None
        existing_payable.qbo_bill_id = invoice.qbo_bill_id
        existing_payable.qbo_vendor_id = invoice.qbo_vendor_id
        payable = existing_payable
    else:
        payables_svc = PayablesService(db, user.id)
        payable = await payables_svc.create_payable(invoice)

    await db.flush()

    # Auto-send to QuickBooks if connected
    try:
        qb_svc = QuickBooksService(db, user.id)
        if await qb_svc.is_connected() and not invoice.qbo_bill_id:
            bill_id, vendor_id = await qb_svc.auto_send_bill(invoice)
            if bill_id:
                # Copy QB IDs to payable (invoice will be deleted)
                payable.qbo_bill_id = bill_id
                payable.qbo_vendor_id = vendor_id
                await db.flush()
                logger.info(f"Auto-sent invoice {invoice.id} to QB as bill {bill_id}")
    except Exception as e:
        logger.error(f"Auto-send to QB failed for invoice {invoice.id}: {e}")
        # Don't fail the approval — QB sync is best-effort

    # Detach payable from invoice before deletion
    payable.invoice_id = None
    await db.flush()

    # Delete attachment file from disk if present
    if invoice.attachment_id:
        att_result = await db.execute(
            select(Attachment).where(Attachment.id == invoice.attachment_id)
        )
        attachment = att_result.scalar_one_or_none()
        if attachment and attachment.file_path:
            import os
            try:
                if os.path.exists(attachment.file_path):
                    os.remove(attachment.file_path)
            except OSError:
                logger.warning(f"Could not delete attachment file: {attachment.file_path}")

    # Hard-delete the invoice (cascades to line items)
    await db.delete(invoice)
    await db.flush()

    return {
        "detail": "Invoice approved and moved to payables",
        "payable_id": payable.id,
        "vendor_name": payable.vendor_name,
        "amount": payable.amount,
    }


@router.get("/{invoice_id}/match-suggestions", response_model=list[JobMatchSuggestion])
async def get_match_suggestions(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get job match suggestions for an invoice."""
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == user.id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    matcher = JobMatchingService(db, user.id)
    suggestions = await matcher.match_invoice(invoice)
    return suggestions


@router.post("/{invoice_id}/junk")
async def junk_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Send an invoice (and its payable) to the junk bin."""
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == user.id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    now = datetime.now(timezone.utc)
    invoice.is_junked = True
    invoice.junked_at = now

    # Also junk the associated payable
    payable_result = await db.execute(
        select(Payable).where(Payable.invoice_id == invoice_id)
    )
    payable = payable_result.scalar_one_or_none()
    if payable:
        payable.is_junked = True
        payable.junked_at = now

    await db.flush()
    return {"detail": "Invoice sent to junk"}


@router.post("/{invoice_id}/restore")
async def restore_invoice(
    invoice_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Restore an invoice (and its payable) from the junk bin."""
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == user.id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    invoice.is_junked = False
    invoice.junked_at = None

    # Also restore the associated payable
    payable_result = await db.execute(
        select(Payable).where(Payable.invoice_id == invoice_id)
    )
    payable = payable_result.scalar_one_or_none()
    if payable:
        payable.is_junked = False
        payable.junked_at = None

    await db.flush()
    return {"detail": "Invoice restored"}
