"""Recurring bills management routes."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.models import User
from app.schemas.schemas import (
    BillOccurrenceListResponse,
    BillOccurrenceSchema,
    CashFlowSummary,
    RecurringBillCreate,
    RecurringBillListResponse,
    RecurringBillSchema,
    RecurringBillUpdate,
)
from app.services.recurring_bills_service import RecurringBillsService
from app.models.models import AppSetting

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recurring-bills", tags=["recurring-bills"])


@router.get("", response_model=RecurringBillListResponse)
async def list_recurring_bills(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all recurring bills."""
    svc = RecurringBillsService(db)
    bills = await svc.list_bills(include_inactive=include_inactive)
    items = [
        RecurringBillSchema(
            id=b.id,
            name=b.name,
            vendor_name=b.vendor_name,
            amount=b.amount,
            frequency=b.frequency.value,
            due_day_of_month=b.due_day_of_month,
            due_month=b.due_month,
            category=b.category.value,
            notes=b.notes,
            is_auto_pay=b.is_auto_pay,
            is_active=b.is_active,
            next_due_date=b.next_due_date,
            alert_days_before=b.alert_days_before,
            created_at=b.created_at,
            updated_at=b.updated_at,
        )
        for b in bills
    ]
    return RecurringBillListResponse(items=items, total=len(items))


@router.post("", response_model=RecurringBillSchema, status_code=201)
async def create_recurring_bill(
    data: RecurringBillCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new recurring bill."""
    svc = RecurringBillsService(db)
    bill = await svc.create_bill(data.model_dump())
    await svc.generate_occurrences()
    await svc.check_overdue()
    await svc.check_due_soon()
    await db.commit()
    return RecurringBillSchema(
        id=bill.id,
        name=bill.name,
        vendor_name=bill.vendor_name,
        amount=bill.amount,
        frequency=bill.frequency.value,
        due_day_of_month=bill.due_day_of_month,
        due_month=bill.due_month,
        category=bill.category.value,
        notes=bill.notes,
        is_auto_pay=bill.is_auto_pay,
        is_active=bill.is_active,
        next_due_date=bill.next_due_date,
        alert_days_before=bill.alert_days_before,
        created_at=bill.created_at,
        updated_at=bill.updated_at,
    )


@router.put("/{bill_id}", response_model=RecurringBillSchema)
async def update_recurring_bill(
    bill_id: int,
    data: RecurringBillUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a recurring bill."""
    svc = RecurringBillsService(db)
    bill = await svc.update_bill(bill_id, data.model_dump(exclude_unset=True))
    if not bill:
        raise HTTPException(status_code=404, detail="Recurring bill not found")
    await db.commit()
    return RecurringBillSchema(
        id=bill.id,
        name=bill.name,
        vendor_name=bill.vendor_name,
        amount=bill.amount,
        frequency=bill.frequency.value,
        due_day_of_month=bill.due_day_of_month,
        due_month=bill.due_month,
        category=bill.category.value,
        notes=bill.notes,
        is_auto_pay=bill.is_auto_pay,
        is_active=bill.is_active,
        next_due_date=bill.next_due_date,
        alert_days_before=bill.alert_days_before,
        created_at=bill.created_at,
        updated_at=bill.updated_at,
    )


@router.delete("/all")
async def delete_all_recurring_bills(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete ALL recurring bills and their occurrences."""
    svc = RecurringBillsService(db)
    count = await svc.delete_all_bills()
    await db.commit()
    return {"detail": f"Deleted {count} bills and all their occurrences"}


@router.delete("/{bill_id}")
async def delete_recurring_bill(
    bill_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Soft-delete a recurring bill."""
    svc = RecurringBillsService(db)
    deleted = await svc.delete_bill(bill_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Recurring bill not found")
    await db.commit()
    return {"detail": "Bill deactivated"}


@router.get("/occurrences", response_model=BillOccurrenceListResponse)
async def list_occurrences(
    start_date: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List bill occurrences with optional filters."""
    svc = RecurringBillsService(db)
    await svc.check_overdue()
    await svc.check_due_soon()
    await db.flush()
    sd = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc) if start_date else None
    ed = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc) if end_date else None
    items = await svc.list_occurrences(
        start_date=sd, end_date=ed, status=status, category=category
    )
    schemas = [BillOccurrenceSchema(**item) for item in items]
    return BillOccurrenceListResponse(items=schemas, total=len(schemas))


@router.post("/occurrences/{occurrence_id}/skip")
async def skip_occurrence(
    occurrence_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Skip a bill occurrence."""
    svc = RecurringBillsService(db)
    occ = await svc.skip_occurrence(occurrence_id)
    if not occ:
        raise HTTPException(status_code=404, detail="Occurrence not found")
    await db.commit()
    return {"detail": "Occurrence skipped"}


@router.post("/occurrences/{occurrence_id}/mark-paid")
async def mark_occurrence_paid(
    occurrence_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark a bill occurrence as paid (local tracking only, not synced to QuickBooks)."""
    svc = RecurringBillsService(db)
    occ = await svc.mark_paid(occurrence_id)
    if not occ:
        raise HTTPException(status_code=404, detail="Occurrence not found")
    await db.commit()
    return {"detail": "Occurrence marked as paid"}


@router.get("/cash-flow", response_model=CashFlowSummary)
async def get_cash_flow(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get cash flow summary."""
    svc = RecurringBillsService(db)
    summary = await svc.get_cash_flow_summary()
    return CashFlowSummary(
        bank_balance=summary["bank_balance"],
        outstanding_checks=summary["outstanding_checks"],
        total_upcoming_7d=summary["total_upcoming_7d"],
        total_upcoming_30d=summary["total_upcoming_30d"],
        total_overdue=summary["total_overdue"],
        real_available=summary["real_available"],
        bills_due_soon=[BillOccurrenceSchema(**b) for b in summary["bills_due_soon"]],
        overdue_bills=[BillOccurrenceSchema(**b) for b in summary["overdue_bills"]],
    )


@router.get("/calendar")
async def get_calendar(
    start_date: str = Query(..., description="ISO date YYYY-MM-DD"),
    end_date: str = Query(..., description="ISO date YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get calendar view of bill occurrences grouped by date."""
    svc = RecurringBillsService(db)
    sd = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
    ed = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
    grouped = await svc.get_calendar_view(sd, ed)
    # Convert to serializable format
    result = {}
    for date_key, occs in grouped.items():
        result[date_key] = [BillOccurrenceSchema(**o).model_dump(mode="json") for o in occs]
    return result


@router.post("/import", status_code=201)
async def bulk_import_bills(
    bills: list[RecurringBillCreate],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Bulk import recurring bills."""
    svc = RecurringBillsService(db)
    created = await svc.bulk_import([b.model_dump() for b in bills])
    await svc.generate_occurrences()
    await svc.check_overdue()
    await svc.check_due_soon()
    await db.commit()
    return {"detail": f"Imported {len(created)} bills", "count": len(created)}


VALID_FREQUENCIES = {"weekly", "monthly", "quarterly", "semi_annual", "annual", "biennial"}
VALID_CATEGORIES = {
    "mortgage", "vehicle", "electric", "water", "sewer", "internet",
    "vehicle_insurance", "health_insurance", "liability_insurance", "life_insurance",
    "credit_card", "bookkeeper", "loan", "subscription", "trash", "phone",
    "workers_comp", "cpa", "taxes", "registration", "license",
    "payroll", "subcontractor", "other",
}


@router.post("/import-csv", status_code=201)
async def import_bills_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Import recurring bills from a CSV file."""
    content = await file.read()
    # Try common encodings
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
    bills_data = []
    errors = []

    for i, row in enumerate(reader, start=2):  # row 2 = first data row after header
        try:
            name = (row.get("name") or "").strip()
            vendor = (row.get("vendor_name") or "").strip()
            amount_str = (row.get("amount") or "").strip()
            frequency = (row.get("frequency") or "monthly").strip().lower()
            due_day_str = (row.get("due_day_of_month") or "").strip()
            due_month_str = (row.get("due_month") or "").strip()
            category = (row.get("category") or "other").strip().lower()
            auto_pay_str = (row.get("is_auto_pay") or "no").strip().lower()
            alert_str = (row.get("alert_days_before") or "7").strip()
            notes = (row.get("notes") or "").strip() or None

            if not name:
                errors.append(f"Row {i}: missing name")
                continue
            if not vendor:
                errors.append(f"Row {i}: missing vendor_name")
                continue
            try:
                amount = float(amount_str)
                if amount <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                errors.append(f"Row {i} ({name}): invalid amount '{amount_str}'")
                continue
            if frequency not in VALID_FREQUENCIES:
                errors.append(f"Row {i} ({name}): invalid frequency '{frequency}'")
                continue
            due_day = None
            if frequency == "weekly":
                # Weekly bills don't need a due_day_of_month
                pass
            elif due_day_str:
                try:
                    due_day = int(due_day_str)
                    if not 1 <= due_day <= 31:
                        raise ValueError
                except (ValueError, TypeError):
                    errors.append(f"Row {i} ({name}): invalid due_day_of_month '{due_day_str}'")
                    continue
            else:
                errors.append(f"Row {i} ({name}): missing due_day_of_month")
                continue
            due_month = None
            if due_month_str:
                try:
                    due_month = int(due_month_str)
                    if not 1 <= due_month <= 12:
                        raise ValueError
                except (ValueError, TypeError):
                    errors.append(f"Row {i} ({name}): invalid due_month '{due_month_str}'")
                    continue
            if category not in VALID_CATEGORIES:
                category = "other"
            is_auto_pay = auto_pay_str in ("yes", "true", "1", "y")
            try:
                alert_days = int(alert_str)
                alert_days = max(1, min(90, alert_days))
            except (ValueError, TypeError):
                alert_days = 7

            bills_data.append({
                "name": name,
                "vendor_name": vendor,
                "amount": amount,
                "frequency": frequency,
                "due_day_of_month": due_day,
                "due_month": due_month,
                "category": category,
                "notes": notes,
                "is_auto_pay": is_auto_pay,
                "alert_days_before": alert_days,
            })
        except Exception as exc:
            errors.append(f"Row {i}: {exc}")

    if not bills_data and errors:
        raise HTTPException(status_code=400, detail=f"No valid bills found. Errors: {'; '.join(errors[:10])}")

    svc = RecurringBillsService(db)
    created = await svc.bulk_import(bills_data)
    await svc.generate_occurrences()
    await svc.check_overdue()
    await svc.check_due_soon()
    await db.commit()

    skipped = len(bills_data) - len(created)
    result = {"detail": f"Imported {len(created)} bills", "count": len(created)}
    if skipped:
        result["skipped"] = skipped
        result["detail"] += f" ({skipped} duplicates skipped)"
    if errors:
        result["warnings"] = errors[:20]
    return result


@router.get("/template-csv")
async def download_template_csv(
    user: User = Depends(get_current_user),
):
    """Download a CSV template pre-filled with common bill types."""
    template_path = Path(__file__).resolve().parent.parent / "recurring_bills_template.csv"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template file not found")
    return FileResponse(
        path=str(template_path),
        media_type="text/csv",
        filename="recurring_bills_template.csv",
    )


@router.post("/outstanding-checks")
async def set_outstanding_checks(
    data: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Set the outstanding checks amount (checks written but not yet cleared)."""
    from sqlalchemy import select as sel
    amount = data.get("amount", 0.0)
    result = await db.execute(
        sel(AppSetting).where(AppSetting.key == "outstanding_checks")
    )
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = str(amount)
    else:
        setting = AppSetting(key="outstanding_checks", value=str(amount))
        db.add(setting)
    await db.commit()
    return {"detail": "Outstanding checks updated", "amount": amount}
