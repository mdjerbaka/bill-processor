"""Receivable checks service."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ReceivableCheck

logger = logging.getLogger(__name__)


class ReceivableChecksService:
    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id

    async def list_checks(self) -> list[ReceivableCheck]:
        result = await self.db.execute(
            select(ReceivableCheck)
            .where(ReceivableCheck.user_id == self.user_id)
            .order_by(ReceivableCheck.job_name.asc())
        )
        return list(result.scalars().all())

    async def get_check(self, check_id: int) -> Optional[ReceivableCheck]:
        result = await self.db.execute(
            select(ReceivableCheck).where(
                ReceivableCheck.id == check_id,
                ReceivableCheck.user_id == self.user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_check(self, data: dict) -> ReceivableCheck:
        check = ReceivableCheck(**data, user_id=self.user_id)
        self.db.add(check)
        await self.db.flush()
        return check

    async def update_check(self, check_id: int, data: dict) -> Optional[ReceivableCheck]:
        check = await self.get_check(check_id)
        if not check:
            return None
        for key, val in data.items():
            setattr(check, key, val)
        await self.db.flush()
        return check

    async def delete_check(self, check_id: int) -> bool:
        check = await self.get_check(check_id)
        if not check:
            return False
        await self.db.delete(check)
        await self.db.flush()
        return True

    async def toggle_collect(self, check_id: int) -> Optional[ReceivableCheck]:
        check = await self.get_check(check_id)
        if not check:
            return None
        check.collect = not check.collect
        await self.db.flush()
        return check

    async def get_totals(self) -> dict:
        """Get total invoiced and total receivables (collect=True)."""
        total_invoiced_result = await self.db.execute(
            select(func.coalesce(func.sum(ReceivableCheck.invoiced_amount), 0.0))
            .where(ReceivableCheck.user_id == self.user_id)
        )
        total_invoiced = float(total_invoiced_result.scalar() or 0.0)

        total_receivables_result = await self.db.execute(
            select(func.coalesce(func.sum(ReceivableCheck.invoiced_amount), 0.0))
            .where(
                ReceivableCheck.collect == True,  # noqa: E712
                ReceivableCheck.user_id == self.user_id,
            )
        )
        total_receivables = float(total_receivables_result.scalar() or 0.0)

        return {
            "total_invoiced": total_invoiced,
            "total_receivables": total_receivables,
        }

    async def bulk_import(self, items: list[dict]) -> int:
        created = 0
        for item in items:
            check = ReceivableCheck(
                job_name=item["job_name"],
                invoiced_amount=item.get("invoiced_amount", 0.0),
                collect=item.get("collect", False),
                notes=item.get("notes"),
                user_id=self.user_id,
            )
            self.db.add(check)
            created += 1
        await self.db.flush()
        return created

    async def delete_all(self) -> int:
        result = await self.db.execute(
            select(func.count(ReceivableCheck.id))
            .where(ReceivableCheck.user_id == self.user_id)
        )
        count = result.scalar() or 0
        await self.db.execute(
            delete(ReceivableCheck).where(ReceivableCheck.user_id == self.user_id)
        )
        await self.db.flush()
        return count
