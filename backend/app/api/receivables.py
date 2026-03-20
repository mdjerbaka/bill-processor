"""Receivable checks management routes."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.models import User
from app.schemas.schemas import (
    ReceivableCheckCreate,
    ReceivableCheckListResponse,
    ReceivableCheckSchema,
    ReceivableCheckUpdate,
)
from app.services.receivable_checks_service import ReceivableChecksService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/receivables", tags=["receivables"])


@router.get("", response_model=ReceivableCheckListResponse)
async def list_receivable_checks(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all receivable checks."""
    svc = ReceivableChecksService(db, user.id)
    checks = await svc.list_checks()
    totals = await svc.get_totals()
    items = [ReceivableCheckSchema.model_validate(c) for c in checks]
    return ReceivableCheckListResponse(
        items=items,
        total=len(items),
        total_invoiced=totals["total_invoiced"],
        total_receivables=totals["total_receivables"],
    )


@router.post("", response_model=ReceivableCheckSchema, status_code=201)
async def create_receivable_check(
    data: ReceivableCheckCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new receivable check entry."""
    svc = ReceivableChecksService(db, user.id)
    check = await svc.create_check(data.model_dump())
    await db.commit()
    await db.refresh(check)
    return ReceivableCheckSchema.model_validate(check)


@router.put("/{check_id}", response_model=ReceivableCheckSchema)
async def update_receivable_check(
    check_id: int,
    data: ReceivableCheckUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a receivable check entry."""
    svc = ReceivableChecksService(db, user.id)
    check = await svc.update_check(check_id, data.model_dump(exclude_unset=True))
    if not check:
        raise HTTPException(status_code=404, detail="Receivable check not found")
    await db.commit()
    await db.refresh(check)
    return ReceivableCheckSchema.model_validate(check)


@router.delete("/{check_id}")
async def delete_receivable_check(
    check_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a receivable check entry."""
    svc = ReceivableChecksService(db, user.id)
    deleted = await svc.delete_check(check_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Receivable check not found")
    await db.commit()
    return {"detail": "Receivable check deleted"}


@router.post("/{check_id}/toggle-collect")
async def toggle_collect(
    check_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Toggle the collect status of a receivable check."""
    svc = ReceivableChecksService(db, user.id)
    check = await svc.toggle_collect(check_id)
    if not check:
        raise HTTPException(status_code=404, detail="Receivable check not found")
    await db.commit()
    return {
        "detail": f"Receivable {'marked for collection' if check.collect else 'removed from collection'}",
        "collect": check.collect,
    }


@router.get("/totals")
async def get_totals(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get total invoiced and total receivables."""
    svc = ReceivableChecksService(db, user.id)
    return await svc.get_totals()


@router.delete("/all")
async def delete_all_receivable_checks(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete ALL receivable checks."""
    svc = ReceivableChecksService(db, user.id)
    count = await svc.delete_all()
    await db.commit()
    return {"detail": f"Deleted {count} receivable checks"}


@router.post("/import-csv", status_code=201)
async def import_receivable_checks_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Import receivable checks from a CSV file.

    Expected columns: job_name, invoiced_amount, collect (yes/no/true/false), notes
    """
    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    items = []
    errors = []
    for i, row in enumerate(reader, start=2):
        job_name = (row.get("job_name") or row.get("Job Name") or row.get("Open Jobs") or "").strip()
        if not job_name:
            errors.append(f"Row {i}: missing job_name")
            continue

        amount_str = (row.get("invoiced_amount") or row.get("Current Invoiced Amount") or row.get("amount") or "0").strip()
        amount_str = amount_str.replace("$", "").replace(",", "")
        try:
            invoiced_amount = float(amount_str)
        except ValueError:
            errors.append(f"Row {i}: invalid amount '{amount_str}'")
            continue

        collect_str = (row.get("collect") or row.get("Collect Yes") or "").strip().lower()
        collect = collect_str in ("yes", "true", "1", "y", "x")

        notes = (row.get("notes") or row.get("Notes") or "").strip() or None

        sent_date_str = (row.get("sent_date") or row.get("Sent Date") or "").strip()
        due_date_str = (row.get("due_date") or row.get("Due Date") or "").strip()
        sent_date = None
        due_date = None
        if sent_date_str:
            try:
                sent_date = datetime.fromisoformat(sent_date_str).replace(tzinfo=timezone.utc)
            except ValueError:
                errors.append(f"Row {i}: invalid sent_date '{sent_date_str}'")
        if due_date_str:
            try:
                due_date = datetime.fromisoformat(due_date_str).replace(tzinfo=timezone.utc)
            except ValueError:
                errors.append(f"Row {i}: invalid due_date '{due_date_str}'")

        items.append({
            "job_name": job_name,
            "invoiced_amount": invoiced_amount,
            "collect": collect,
            "sent_date": sent_date,
            "due_date": due_date,
            "notes": notes,
        })

    svc = ReceivableChecksService(db, user.id)
    count = await svc.bulk_import(items)
    await db.commit()

    result = {"detail": f"Imported {count} receivable checks", "count": count}
    if errors:
        result["warnings"] = errors[:20]
    return result
