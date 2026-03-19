"""Payments Out service — tracks checks/ACH/online payments not yet cleared."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import PaymentOut, PaymentOutStatus, PaymentMethod


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
