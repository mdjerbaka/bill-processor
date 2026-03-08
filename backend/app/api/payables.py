"""Payables management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.models import AppSetting, Invoice, InvoiceStatus, Job, Payable, PayableStatus, User
from app.schemas.schemas import (
    BankBalanceRequest,
    PayableListResponse,
    PayableSchema,
    RealBalanceResponse,
)
from app.services.payables_service import PayablesService
from app.services.quickbooks_service import QuickBooksService

logger = __import__('logging').getLogger(__name__)

router = APIRouter(prefix="/payables", tags=["payables"])


@router.get("", response_model=PayableListResponse)
async def list_payables(
    include_paid: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List payables with summary."""
    query = (
        select(Payable, Invoice, Job)
        .join(Invoice, Payable.invoice_id == Invoice.id)
        .outerjoin(Job, Invoice.job_id == Job.id)
        .where(Payable.is_junked == False)
    )
    if not include_paid:
        query = query.where(
            Payable.status.in_([PayableStatus.OUTSTANDING, PayableStatus.OVERDUE])
        )
    query = query.order_by(Payable.due_date.asc())

    result = await db.execute(query)
    rows = result.all()

    svc = PayablesService(db)
    summary = await svc.get_payables_summary()

    items = [
        PayableSchema(
            id=p.id,
            invoice_id=p.invoice_id,
            vendor_name=p.vendor_name,
            amount=p.amount,
            due_date=p.due_date,
            status=p.status.value,
            paid_at=p.paid_at,
            created_at=p.created_at,
            invoice_number=inv.invoice_number,
            job_name=job.name if job else None,
        )
        for p, inv, job in rows
    ]

    return PayableListResponse(
        items=items,
        total=len(items),
        total_outstanding=summary["total_outstanding"],
        total_overdue=summary["total_overdue"],
    )


@router.post("/{payable_id}/mark-paid", response_model=PayableSchema)
async def mark_payable_paid(
    payable_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark a payable as paid (also marks the linked invoice as paid)."""
    svc = PayablesService(db)
    payable = await svc.mark_paid(payable_id)
    if not payable:
        raise HTTPException(status_code=404, detail="Payable not found")

    # Also mark the linked invoice as paid
    inv_result = await db.execute(
        select(Invoice, Job)
        .outerjoin(Job, Invoice.job_id == Job.id)
        .where(Invoice.id == payable.invoice_id)
    )
    row = inv_result.one_or_none()
    inv, job = row if row else (None, None)
    if inv and inv.status != InvoiceStatus.PAID:
        inv.status = InvoiceStatus.PAID
        await db.flush()

        # Sync payment to QuickBooks if connected
        try:
            qb_svc = QuickBooksService(db)
            if await qb_svc.is_connected():
                # If bill wasn't sent to QB yet, send it now
                if not inv.qbo_bill_id:
                    bill_id, vendor_id = await qb_svc.auto_send_bill(inv)
                    if bill_id:
                        inv.qbo_bill_id = bill_id
                        inv.qbo_vendor_id = vendor_id
                        await db.flush()
                        logger.info(f"Sent invoice {inv.id} to QB as bill {bill_id} (on mark-paid)")
                # Now mark the QB bill as paid
                if inv.qbo_bill_id:
                    payment_id = await qb_svc.auto_pay_bill(inv)
                    if payment_id:
                        inv.qbo_payment_id = payment_id
                        await db.flush()
                        logger.info(f"Synced payment to QB for invoice {inv.id}, payment {payment_id}")
                    else:
                        logger.warning(
                            f"QB payment sync returned no payment ID for invoice {inv.id} "
                            f"(qbo_bill_id={inv.qbo_bill_id}, qbo_vendor_id={inv.qbo_vendor_id})"
                        )
                else:
                    logger.warning(f"No QBO bill ID after send attempt for invoice {inv.id}, skipping payment")
        except Exception as e:
            logger.error(f"QB payment sync failed for invoice {inv.id}: {e}")

    return PayableSchema(
        id=payable.id,
        invoice_id=payable.invoice_id,
        vendor_name=payable.vendor_name,
        amount=payable.amount,
        due_date=payable.due_date,
        status=payable.status.value,
        paid_at=payable.paid_at,
        created_at=payable.created_at,
        invoice_number=inv.invoice_number if inv else None,
        job_name=job.name if job else None,
    )


@router.post("/{payable_id}/junk")
async def junk_payable(
    payable_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Send a payable to the junk bin and revert invoice to review."""
    result = await db.execute(
        select(Payable).where(Payable.id == payable_id)
    )
    payable = result.scalar_one_or_none()
    if not payable:
        raise HTTPException(status_code=404, detail="Payable not found")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    payable.is_junked = True
    payable.junked_at = now

    # Revert the invoice status so the user can re-approve later
    inv_result = await db.execute(
        select(Invoice).where(Invoice.id == payable.invoice_id)
    )
    invoice = inv_result.scalar_one_or_none()
    if invoice and invoice.status in (
        InvoiceStatus.APPROVED, InvoiceStatus.SENT_TO_QB, InvoiceStatus.PAID
    ):
        invoice.status = InvoiceStatus.NEEDS_REVIEW

    await db.flush()
    return {"detail": "Payable sent to junk"}


@router.post("/{payable_id}/restore")
async def restore_payable(
    payable_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Restore a payable from the junk bin."""
    result = await db.execute(
        select(Payable).where(Payable.id == payable_id)
    )
    payable = result.scalar_one_or_none()
    if not payable:
        raise HTTPException(status_code=404, detail="Payable not found")

    payable.is_junked = False
    payable.junked_at = None
    await db.flush()
    return {"detail": "Payable restored"}


@router.post("/bank-balance", response_model=RealBalanceResponse)
async def set_bank_balance(
    req: BankBalanceRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Set the current bank balance and get real available funds."""
    # Upsert bank balance setting
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == "bank_balance")
    )
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = str(req.bank_balance)
    else:
        setting = AppSetting(key="bank_balance", value=str(req.bank_balance))
        db.add(setting)
    await db.flush()

    svc = PayablesService(db)
    balance = await svc.get_real_balance()
    return RealBalanceResponse(**balance)


@router.get("/real-balance", response_model=RealBalanceResponse)
async def get_real_balance(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get current real available funds."""
    svc = PayablesService(db)
    balance = await svc.get_real_balance()
    return RealBalanceResponse(**balance)


@router.get("/export")
async def export_payables_excel(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Export payables to Excel (.xlsx)."""
    svc = PayablesService(db)
    excel_bytes = await svc.export_to_excel()

    return StreamingResponse(
        iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=real_bank_balance.xlsx"
        },
    )


@router.post("/backfill")
async def backfill_missing_payables(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create payable records for invoices that should have them but don't.

    Covers invoices in AUTO_MATCHED, APPROVED, SENT_TO_QB, or PAID status
    that were processed before payable creation was added to those flows.
    """
    from sqlalchemy import and_

    # Find invoices in relevant statuses that have no payable
    subq = select(Payable.invoice_id)
    result = await db.execute(
        select(Invoice).where(
            and_(
                Invoice.status.in_([
                    InvoiceStatus.AUTO_MATCHED,
                    InvoiceStatus.APPROVED,
                    InvoiceStatus.SENT_TO_QB,
                    InvoiceStatus.PAID,
                ]),
                Invoice.is_junked == False,
                Invoice.id.not_in(subq),
            )
        )
    )
    orphan_invoices = list(result.scalars().all())

    svc = PayablesService(db)
    created = 0
    for inv in orphan_invoices:
        try:
            payable = await svc.create_payable(inv)
            # If the invoice is already paid, mark the payable as paid too
            if inv.status == InvoiceStatus.PAID:
                await svc.mark_paid(payable.id)
            created += 1
        except Exception as e:
            logger.error(f"Backfill failed for invoice {inv.id}: {e}")

    await db.flush()
    logger.info(f"Backfilled {created} payables for {len(orphan_invoices)} orphan invoices")
    return {"backfilled": created, "total_orphans": len(orphan_invoices)}
