"""Junk bin API – lists all soft-deleted items across entity types."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.models import Invoice, Job, Payable, User

router = APIRouter(prefix="/junk", tags=["junk"])


@router.get("")
async def list_junk(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all junked invoices, payables, and jobs."""
    # Junked invoices
    inv_result = await db.execute(
        select(Invoice)
        .options(joinedload(Invoice.job))
        .where(Invoice.is_junked == True, Invoice.user_id == user.id)
        .order_by(Invoice.junked_at.desc())
    )
    invoices = inv_result.unique().scalars().all()

    # Junked payables (stand-alone, not already covered by invoice junk)
    pay_result = await db.execute(
        select(Payable)
        .where(Payable.is_junked == True, Payable.user_id == user.id)
        .order_by(Payable.junked_at.desc())
    )
    payables = pay_result.scalars().all()

    # Junked jobs
    job_result = await db.execute(
        select(Job)
        .where(Job.is_junked == True, Job.user_id == user.id)
        .order_by(Job.junked_at.desc())
    )
    jobs = job_result.scalars().all()

    return {
        "invoices": [
            {
                "id": inv.id,
                "type": "invoice",
                "vendor_name": inv.vendor_name,
                "invoice_number": inv.invoice_number,
                "total_amount": inv.total_amount,
                "job_name": inv.job.name if inv.job else None,
                "status": inv.status.value,
                "junked_at": inv.junked_at.isoformat() if inv.junked_at else None,
            }
            for inv in invoices
        ],
        "payables": [
            {
                "id": p.id,
                "type": "payable",
                "vendor_name": p.vendor_name,
                "amount": p.amount,
                "due_date": p.due_date.isoformat() if p.due_date else None,
                "status": p.status.value,
                "junked_at": p.junked_at.isoformat() if p.junked_at else None,
            }
            for p in payables
        ],
        "jobs": [
            {
                "id": j.id,
                "type": "job",
                "name": j.name,
                "code": j.code,
                "junked_at": j.junked_at.isoformat() if j.junked_at else None,
            }
            for j in jobs
        ],
    }
