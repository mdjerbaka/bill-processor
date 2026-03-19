"""Payables management routes."""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.models import AppSetting, Invoice, InvoiceStatus, Job, Payable, PayableStatus, User
from app.schemas.schemas import (
    BankBalanceRequest,
    BufferRequest,
    PayableCreateRequest,
    PayableListResponse,
    PayableSchema,
    PayableUpdateRequest,
    RealBalanceResponse,
)
from app.services.payables_service import PayablesService

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
        .outerjoin(Invoice, Payable.invoice_id == Invoice.id)
        .outerjoin(Job, Invoice.job_id == Job.id)
        .where(Payable.is_junked == False, Payable.user_id == user.id)
    )
    if not include_paid:
        query = query.where(
            Payable.status.in_([PayableStatus.OUTSTANDING, PayableStatus.OVERDUE])
        )
    query = query.order_by(Payable.due_date.asc())

    result = await db.execute(query)
    rows = result.all()

    svc = PayablesService(db, user.id)
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
            invoice_number=inv.invoice_number if inv else None,
            job_name=job.name if job else None,
            is_permanent=p.is_permanent,
        )
        for p, inv, job in rows
    ]

    return PayableListResponse(
        items=items,
        total=len(items),
        total_outstanding=summary["total_outstanding"],
        total_overdue=summary["total_overdue"],
    )


@router.post("", response_model=PayableSchema)
async def create_payable(
    req: PayableCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Manually create a payable (not linked to an invoice)."""
    payable = Payable(
        vendor_name=req.vendor_name,
        amount=req.amount,
        due_date=req.due_date,
        status=PayableStatus(req.status) if req.status else PayableStatus.OUTSTANDING,
        is_permanent=req.is_permanent if req.is_permanent else False,
        user_id=user.id,
    )
    db.add(payable)
    await db.commit()
    return PayableSchema(
        id=payable.id,
        invoice_id=payable.invoice_id,
        vendor_name=payable.vendor_name,
        amount=payable.amount,
        due_date=payable.due_date,
        status=payable.status.value,
        paid_at=payable.paid_at,
        created_at=payable.created_at,
        invoice_number=req.invoice_number,
        job_name=None,
        is_permanent=payable.is_permanent,
    )


@router.put("/{payable_id}", response_model=PayableSchema)
async def update_payable(
    payable_id: int,
    req: PayableUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a payable's fields."""
    result = await db.execute(
        select(Payable).where(Payable.id == payable_id, Payable.user_id == user.id)
    )
    payable = result.scalar_one_or_none()
    if not payable:
        raise HTTPException(status_code=404, detail="Payable not found")

    update_data = req.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "status" and value is not None:
            payable.status = PayableStatus(value)
            if value == "paid":
                payable.paid_at = datetime.now(timezone.utc)
        elif field == "invoice_number":
            # invoice_number is stored on the linked invoice, skip for standalone
            continue
        else:
            setattr(payable, field, value)

    await db.flush()

    # Fetch invoice info if linked
    inv_number = None
    job_name = None
    if payable.invoice_id:
        inv_result = await db.execute(
            select(Invoice, Job)
            .outerjoin(Job, Invoice.job_id == Job.id)
            .where(Invoice.id == payable.invoice_id)
        )
        row = inv_result.first()
        if row:
            inv_number = row[0].invoice_number
            job_name = row[1].name if row[1] else None

    return PayableSchema(
        id=payable.id,
        invoice_id=payable.invoice_id,
        vendor_name=payable.vendor_name,
        amount=payable.amount,
        due_date=payable.due_date,
        status=payable.status.value,
        paid_at=payable.paid_at,
        created_at=payable.created_at,
        invoice_number=inv_number,
        job_name=job_name,
        is_permanent=payable.is_permanent,
    )


@router.post("/{payable_id}/mark-paid")
async def mark_payable_paid(
    payable_id: int,
    body: dict = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark a payable as paid, optionally creating a Payment Out record."""
    result = await db.execute(
        select(Payable).where(Payable.id == payable_id, Payable.user_id == user.id)
    )
    payable = result.scalar_one_or_none()
    if not payable:
        raise HTTPException(status_code=404, detail="Payable not found")

    if payable.is_permanent:
        raise HTTPException(status_code=400, detail="Permanent payables cannot be marked as paid")

    payable.status = PayableStatus.PAID
    payable.paid_at = datetime.now(timezone.utc)
    await db.flush()

    # Optionally create a Payment Out record if payment details provided
    payment_out_id = None
    if body and body.get("payment_method"):
        from app.services.payments_out_service import PaymentsOutService
        po_svc = PaymentsOutService(db, user.id)
        po = await po_svc.create({
            "vendor_name": payable.vendor_name,
            "amount": payable.amount,
            "payment_date": datetime.now(timezone.utc),
            "payment_method": body.get("payment_method", "other"),
            "check_number": body.get("check_number"),
            "job_name": body.get("job_name"),
            "notes": body.get("notes"),
            "payable_id": payable.id,
        })
        payment_out_id = po.id
        await db.flush()

    return {"detail": "Payable marked as paid", "payment_out_id": payment_out_id}


@router.post("/{payable_id}/junk")
async def junk_payable(
    payable_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Send a payable to the junk bin and revert invoice to review."""
    result = await db.execute(
        select(Payable).where(Payable.id == payable_id, Payable.user_id == user.id)
    )
    payable = result.scalar_one_or_none()
    if not payable:
        raise HTTPException(status_code=404, detail="Payable not found")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    payable.is_junked = True
    payable.junked_at = now

    # Revert the invoice status so the user can re-approve later
    if payable.invoice_id:
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
        select(Payable).where(Payable.id == payable_id, Payable.user_id == user.id)
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
        select(AppSetting).where(AppSetting.key == "bank_balance", AppSetting.user_id == user.id)
    )
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = str(req.bank_balance)
    else:
        setting = AppSetting(key="bank_balance", value=str(req.bank_balance), user_id=user.id)
        db.add(setting)
    await db.flush()

    svc = PayablesService(db, user.id)
    balance = await svc.get_real_balance()
    return RealBalanceResponse(**balance)


@router.post("/buffer", response_model=RealBalanceResponse)
async def set_buffer(
    req: BufferRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Set the balance buffer and get updated real available funds."""
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == "balance_buffer", AppSetting.user_id == user.id)
    )
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = str(req.buffer)
    else:
        setting = AppSetting(key="balance_buffer", value=str(req.buffer), user_id=user.id)
        db.add(setting)
    await db.flush()

    svc = PayablesService(db, user.id)
    balance = await svc.get_real_balance()
    return RealBalanceResponse(**balance)


@router.get("/real-balance", response_model=RealBalanceResponse)
async def get_real_balance(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get current real available funds."""
    svc = PayablesService(db, user.id)
    balance = await svc.get_real_balance()
    return RealBalanceResponse(**balance)


@router.get("/export")
async def export_payables_excel(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Export payables to Excel (.xlsx)."""
    svc = PayablesService(db, user.id)
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

    svc = PayablesService(db, user.id)
    created = 0
    for inv in orphan_invoices:
        try:
            payable = await svc.create_payable(inv)
            # If the invoice is already paid, mark the payable as paid too
            if inv.status == InvoiceStatus.PAID:
                payable.status = PayableStatus.PAID
                payable.paid_at = datetime.now(timezone.utc)
                await db.flush()
            created += 1
        except Exception as e:
            logger.error(f"Backfill failed for invoice {inv.id}: {e}")

    await db.flush()
    logger.info(f"Backfilled {created} payables for {len(orphan_invoices)} orphan invoices")
    return {"backfilled": created, "total_orphans": len(orphan_invoices)}


@router.get("/template-csv")
async def download_payables_template():
    """Download a CSV template for payable imports."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["vendor_name", "amount", "due_date", "status", "is_permanent", "notes"])
    writer.writerow(["Acme Supplies", "1500.00", "2026-04-15", "outstanding", "no", "Monthly materials"])
    writer.writerow(["Payroll - Crew A", "5000.00", "", "outstanding", "yes", "Weekly payroll"])
    writer.writerow(["Equipment Rental", "800.00", "2026-04-01", "outstanding", "no", ""])
    content = output.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=payables_template.csv"},
    )


_MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_flexible_date(s: str) -> datetime:
    """Parse dates in various formats: YYYY-MM-DD, M/D/YYYY, D-Mon, Mon-D, etc."""
    s = s.strip()
    # ISO: 2026-03-16
    try:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    # US slash: 3/16/2026 or 03/16/2026
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', s)
    if m:
        return datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)), tzinfo=timezone.utc)
    # Abbreviated month: 16-Mar, Mar-16, 16 Mar, Mar 16
    m = re.match(r'^(\d{1,2})[\s\-]([A-Za-z]{3})$', s)
    if m:
        day, mon = int(m.group(1)), _MONTH_ABBR.get(m.group(2).lower())
        if mon:
            return datetime(datetime.now().year, mon, day, tzinfo=timezone.utc)
    m = re.match(r'^([A-Za-z]{3})[\s\-](\d{1,2})$', s)
    if m:
        mon, day = _MONTH_ABBR.get(m.group(1).lower()), int(m.group(2))
        if mon:
            return datetime(datetime.now().year, mon, day, tzinfo=timezone.utc)
    # D/M/YYYY variant (less common, try last)
    m = re.match(r'^(\d{1,2})-(\d{1,2})-(\d{4})$', s)
    if m:
        return datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)), tzinfo=timezone.utc)
    raise ValueError(f"Unrecognized date format: {s}")


@router.post("/import-csv", status_code=201)
async def import_payables_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Import payables from a CSV file."""
    content = await file.read()
    text = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = content.decode(encoding)
            break
        except (UnicodeDecodeError, ValueError):
            continue
    if text is None:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    errors = []
    created_count = 0

    for i, row in enumerate(reader, start=2):
        try:
            vendor = (row.get("vendor_name") or "").strip()
            amount_str = (row.get("amount") or "").strip()
            due_date_str = (row.get("due_date") or "").strip()
            status_str = (row.get("status") or "outstanding").strip().lower()
            permanent_str = (row.get("is_permanent") or "no").strip().lower()
            notes = (row.get("notes") or "").strip() or None

            if not vendor:
                errors.append(f"Row {i}: missing vendor_name")
                continue
            try:
                amount = float(amount_str)
                if amount <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                errors.append(f"Row {i} ({vendor}): invalid amount '{amount_str}'")
                continue

            due_date = None
            if due_date_str:
                try:
                    due_date = _parse_flexible_date(due_date_str)
                except ValueError:
                    errors.append(f"Row {i} ({vendor}): invalid date '{due_date_str}'")
                    continue

            if status_str not in ("outstanding", "overdue", "scheduled"):
                status_str = "outstanding"

            is_permanent = permanent_str in ("yes", "true", "1", "y")

            payable = Payable(
                vendor_name=vendor,
                amount=amount,
                due_date=due_date,
                status=PayableStatus(status_str),
                is_permanent=is_permanent,
                user_id=user.id,
            )
            db.add(payable)
            created_count += 1
        except Exception as exc:
            errors.append(f"Row {i}: {exc}")

    if created_count == 0 and errors:
        raise HTTPException(status_code=400, detail=f"No valid payables found. Errors: {'; '.join(errors[:10])}")

    await db.flush()
    result = {"detail": f"Imported {created_count} payables", "count": created_count}
    if errors:
        result["warnings"] = errors[:20]
    return result
