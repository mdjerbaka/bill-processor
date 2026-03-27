"""Payments Out service — tracks checks/ACH/online payments not yet cleared."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select, union_all, literal, case, String, Float, DateTime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.models import (
    PaymentOut,
    PaymentOutStatus,
    PaymentMethod,
    Payable,
    PayableStatus,
    BillOccurrence,
    OccurrenceStatus,
    RecurringBill,
)


class PaymentsOutService:
    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id

    async def list_outstanding(self) -> list[PaymentOut]:
        result = await self.db.execute(
            select(PaymentOut)
            .where(
                PaymentOut.user_id == self.user_id,
                PaymentOut.status == PaymentOutStatus.OUTSTANDING,
            )
            .order_by(PaymentOut.payment_date.desc())
        )
        return list(result.scalars().all())

    async def list_cleared(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[PaymentOut]:
        q = select(PaymentOut).where(
            PaymentOut.user_id == self.user_id,
            PaymentOut.status == PaymentOutStatus.CLEARED,
        )
        if start_date:
            q = q.where(PaymentOut.cleared_at >= start_date)
        if end_date:
            q = q.where(PaymentOut.cleared_at <= end_date)
        q = q.order_by(PaymentOut.cleared_at.desc())
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def create(self, data: dict) -> PaymentOut:
        payment = PaymentOut(
            user_id=self.user_id,
            vendor_name=data["vendor_name"],
            amount=data["amount"],
            payment_date=data["payment_date"],
            payment_method=PaymentMethod(data.get("payment_method", "other")),
            check_number=data.get("check_number"),
            job_name=data.get("job_name"),
            notes=data.get("notes"),
            payable_id=data.get("payable_id"),
            status=PaymentOutStatus.OUTSTANDING,
        )
        self.db.add(payment)
        await self.db.flush()
        return payment

    async def update(self, payment_id: int, data: dict) -> Optional[PaymentOut]:
        result = await self.db.execute(
            select(PaymentOut).where(
                PaymentOut.id == payment_id,
                PaymentOut.user_id == self.user_id,
            )
        )
        payment = result.scalar_one_or_none()
        if not payment:
            return None
        for field, value in data.items():
            if field == "payment_method" and value is not None:
                payment.payment_method = PaymentMethod(value)
            elif value is not None:
                setattr(payment, field, value)
        payment.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return payment

    async def delete(self, payment_id: int) -> bool:
        result = await self.db.execute(
            select(PaymentOut).where(
                PaymentOut.id == payment_id,
                PaymentOut.user_id == self.user_id,
            )
        )
        payment = result.scalar_one_or_none()
        if not payment:
            return False
        await self.db.delete(payment)
        await self.db.flush()
        return True

    async def mark_cleared(self, payment_id: int) -> Optional[PaymentOut]:
        result = await self.db.execute(
            select(PaymentOut).where(
                PaymentOut.id == payment_id,
                PaymentOut.user_id == self.user_id,
            )
        )
        payment = result.scalar_one_or_none()
        if not payment:
            return None
        payment.status = PaymentOutStatus.CLEARED
        payment.cleared_at = datetime.now(timezone.utc)
        payment.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return payment

    async def get_total_outstanding(self) -> float:
        result = await self.db.execute(
            select(func.coalesce(func.sum(PaymentOut.amount), 0.0)).where(
                PaymentOut.user_id == self.user_id,
                PaymentOut.status == PaymentOutStatus.OUTSTANDING,
            )
        )
        return float(result.scalar() or 0.0)

    async def get_combined_payment_history(
        self,
        search: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> dict:
        """Return a combined list of all paid items: cleared PaymentOut, paid Payable, paid BillOccurrence."""
        # --- PaymentOut (cleared) ---
        po_q = (
            select(
                PaymentOut.id.label("id"),
                PaymentOut.cleared_at.label("date"),
                PaymentOut.vendor_name.label("vendor"),
                PaymentOut.amount.label("amount"),
                literal("payment_out").label("type"),
                PaymentOut.payment_method.label("method"),
                PaymentOut.check_number.label("reference"),
                PaymentOut.job_name.label("job_name"),
                PaymentOut.notes.label("notes"),
            )
            .where(
                PaymentOut.user_id == self.user_id,
                PaymentOut.status == PaymentOutStatus.CLEARED,
            )
        )

        # --- Payable (paid) ---
        pay_q = (
            select(
                Payable.id.label("id"),
                Payable.paid_at.label("date"),
                Payable.vendor_name.label("vendor"),
                Payable.amount.label("amount"),
                literal("payable").label("type"),
                literal(None).label("method"),
                Payable.invoice_number.label("reference"),
                Payable.job_name.label("job_name"),
                literal(None).label("notes"),
            )
            .where(
                Payable.user_id == self.user_id,
                Payable.status == PayableStatus.PAID,
            )
        )

        # --- BillOccurrence (paid) ---
        bill_q = (
            select(
                BillOccurrence.id.label("id"),
                BillOccurrence.paid_at.label("date"),
                RecurringBill.vendor_name.label("vendor"),
                BillOccurrence.amount.label("amount"),
                literal("bill").label("type"),
                literal(None).label("method"),
                RecurringBill.name.label("reference"),
                literal(None).label("job_name"),
                BillOccurrence.notes.label("notes"),
            )
            .join(RecurringBill, BillOccurrence.recurring_bill_id == RecurringBill.id)
            .where(
                RecurringBill.user_id == self.user_id,
                BillOccurrence.status == OccurrenceStatus.PAID,
            )
        )

        combined = union_all(po_q, pay_q, bill_q).subquery()

        # Apply filters
        q = select(combined)
        if search:
            pattern = f"%{search}%"
            q = q.where(
                combined.c.vendor.ilike(pattern)
                | combined.c.reference.ilike(pattern)
                | combined.c.job_name.ilike(pattern)
                | combined.c.notes.ilike(pattern)
            )
        if start_date:
            q = q.where(combined.c.date >= start_date)
        if end_date:
            q = q.where(combined.c.date <= end_date)

        # Get total count and amount
        count_q = select(func.count(), func.coalesce(func.sum(combined.c.amount), 0.0)).select_from(q.subquery())
        count_result = await self.db.execute(count_q)
        total_count, total_amount = count_result.one()

        # Paginate
        offset = (page - 1) * per_page
        q = q.order_by(combined.c.date.desc()).limit(per_page).offset(offset)

        result = await self.db.execute(q)
        rows = result.all()

        items = []
        for row in rows:
            items.append({
                "id": row.id,
                "date": row.date,
                "vendor": row.vendor,
                "amount": float(row.amount),
                "type": row.type,
                "method": row.method.value if hasattr(row.method, "value") else row.method,
                "reference": row.reference,
                "job_name": row.job_name,
                "notes": row.notes,
            })

        return {
            "items": items,
            "total": int(total_count),
            "total_amount": float(total_amount),
        }
