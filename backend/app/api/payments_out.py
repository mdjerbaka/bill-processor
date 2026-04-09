"""Payments Out management routes — check register / payment tracking."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.models import User
from app.schemas.schemas import (
    PaymentOutCreate,
    PaymentOutListResponse,
    PaymentOutSchema,
    PaymentOutUpdate,
    CombinedPaymentListResponse,
)
from app.services.payments_out_service import PaymentsOutService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments-out", tags=["payments-out"])


def _to_schema(p) -> PaymentOutSchema:
    return PaymentOutSchema(
        id=p.id,
        vendor_name=p.vendor_name,
        amount=p.amount,
        payment_date=p.payment_date,
        payment_method=p.payment_method.value,
        check_number=p.check_number,
        job_name=p.job_name,
        notes=p.notes,
        status=p.status.value,
        cleared_at=p.cleared_at,
        payable_id=p.payable_id,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("", response_model=PaymentOutListResponse)
async def list_outstanding_payments(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List outstanding (uncleared) payments."""
    svc = PaymentsOutService(db, user.id)
    payments = await svc.list_outstanding()
    total = await svc.get_total_outstanding()
    items = [_to_schema(p) for p in payments]
    total_paid = sum(p.amount for p in payments)
    return PaymentOutListResponse(items=items, total=total_paid, total_outstanding=total)


@router.get("/history", response_model=PaymentOutListResponse)
async def list_cleared_payments(
    start_date: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List cleared payments (Running Payments List)."""
    svc = PaymentsOutService(db, user.id)
    sd = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc) if start_date else None
    ed = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc) if end_date else None
    payments = await svc.list_cleared(start_date=sd, end_date=ed)
    items = [_to_schema(p) for p in payments]
    total_cleared = sum(p.amount for p in payments)
    return PaymentOutListResponse(items=items, total=total_cleared, total_outstanding=0)


@router.get("/all-history", response_model=CombinedPaymentListResponse)
async def all_payment_history(
    search: Optional[str] = Query(None, description="Search vendor, reference, job, notes"),
    start_date: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Combined history of all payments: cleared PaymentOuts, paid Payables, paid BillOccurrences."""
    svc = PaymentsOutService(db, user.id)
    sd = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc) if start_date else None
    ed = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc) if end_date else None
    result = await svc.get_combined_payment_history(
        search=search, start_date=sd, end_date=ed, page=page, per_page=per_page,
    )
    return CombinedPaymentListResponse(**result)


@router.get("/total-outstanding")
async def get_total_outstanding(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get sum of all outstanding (uncleared) payments."""
    svc = PaymentsOutService(db, user.id)
    total = await svc.get_total_outstanding()
    return {"total_outstanding": total}


@router.post("", response_model=PaymentOutSchema, status_code=201)
async def create_payment_out(
    data: PaymentOutCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new payment out record."""
    svc = PaymentsOutService(db, user.id)
    payment = await svc.create(data.model_dump())
    await db.commit()
    return _to_schema(payment)


@router.put("/{payment_id}", response_model=PaymentOutSchema)
async def update_payment_out(
    payment_id: int,
    data: PaymentOutUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a payment out record."""
    svc = PaymentsOutService(db, user.id)
    payment = await svc.update(payment_id, data.model_dump(exclude_unset=True))
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    await db.commit()
    return _to_schema(payment)


@router.delete("/{payment_id}")
async def delete_payment_out(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a payment out record."""
    svc = PaymentsOutService(db, user.id)
    deleted = await svc.delete(payment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Payment not found")
    await db.commit()
    return {"detail": "Payment deleted"}


@router.post("/{payment_id}/mark-cleared")
async def mark_payment_cleared(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark a payment as cleared (showed up in bank feed)."""
    svc = PaymentsOutService(db, user.id)
    payment = await svc.mark_cleared(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    await db.commit()
    return {"detail": "Payment marked as cleared", "cleared_at": payment.cleared_at.isoformat()}


@router.post("/{payment_id}/unmark-cleared")
async def unmark_payment_cleared(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Revert a cleared payment back to outstanding."""
    svc = PaymentsOutService(db, user.id)
    payment = await svc.unmark_cleared(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    await db.commit()
    return {"detail": "Payment reverted to outstanding"}


@router.post("/import-csv", status_code=201)
async def import_payments_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Import payments from a CSV file."""
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
    svc = PaymentsOutService(db, user.id)
    created_count = 0
    valid_methods = {"check", "ach", "debit", "online", "wire", "other"}

    for i, row in enumerate(reader, start=2):
        try:
            vendor = (row.get("vendor_name") or row.get("to_who") or "").strip()
            amount_str = (row.get("amount") or "").strip()
            date_str = (row.get("payment_date") or row.get("date") or "").strip()
            method = (row.get("payment_method") or "other").strip().lower()
            check_num = (row.get("check_number") or row.get("check_or_online") or "").strip() or None
            job = (row.get("job_name") or row.get("for_job") or "").strip() or None
            notes = (row.get("notes") or "").strip() or None

            if not vendor:
                errors.append(f"Row {i}: missing vendor_name")
                continue
            try:
                amount = float(amount_str.replace(",", "").replace("$", ""))
                if amount <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                errors.append(f"Row {i} ({vendor}): invalid amount '{amount_str}'")
                continue
            if not date_str:
                errors.append(f"Row {i} ({vendor}): missing date")
                continue
            try:
                payment_date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
            except ValueError:
                # Try common US format
                try:
                    payment_date = datetime.strptime(date_str, "%m/%d/%Y").replace(tzinfo=timezone.utc)
                except ValueError:
                    errors.append(f"Row {i} ({vendor}): invalid date '{date_str}'")
                    continue

            if method not in valid_methods:
                method = "other"

            await svc.create({
                "vendor_name": vendor,
                "amount": amount,
                "payment_date": payment_date,
                "payment_method": method,
                "check_number": check_num,
                "job_name": job,
                "notes": notes,
            })
            created_count += 1
        except Exception as exc:
            errors.append(f"Row {i}: {exc}")

    if created_count == 0 and errors:
        raise HTTPException(status_code=400, detail=f"No valid payments found. Errors: {'; '.join(errors[:10])}")

    await db.commit()
    result = {"detail": f"Imported {created_count} payments", "count": created_count}
    if errors:
        result["warnings"] = errors[:20]
    return result


@router.get("/template-csv")
async def download_payments_template(
    user: User = Depends(get_current_user),
):
    """Download a CSV template for payment imports."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["check_number", "vendor_name", "job_name", "payment_date", "amount", "payment_method", "notes"])
    writer.writerow(["1873", "Commonwealth of Mass", "Annual report filing", "2026-03-17", "125.00", "check", "mailed to secretary of state's office"])
    writer.writerow(["1868", "Real Mass", "20 Hunter Skiing", "2026-03-13", "10000.00", "check", "Real Mass picked up at office"])
    writer.writerow(["", "Verizon", "Office", "2026-03-15", "185.50", "ach", "auto-pay"])
    content_bytes = output.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        iter([content_bytes]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=payments_out_template.csv"},
    )
