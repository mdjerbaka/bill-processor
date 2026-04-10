"""Vendor accounts (top vendor accounts) service."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import VendorAccount

logger = logging.getLogger(__name__)


class VendorAccountsService:
    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id

    async def list_accounts(self) -> list[VendorAccount]:
        result = await self.db.execute(
            select(VendorAccount)
            .where(VendorAccount.user_id == self.user_id)
            .order_by(VendorAccount.sort_order.asc(), VendorAccount.vendor_name.asc())
        )
        return list(result.scalars().all())

    async def get_account(self, account_id: int) -> Optional[VendorAccount]:
        result = await self.db.execute(
            select(VendorAccount).where(
                VendorAccount.id == account_id,
                VendorAccount.user_id == self.user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_account(self, data: dict) -> VendorAccount:
        account = VendorAccount(**data, user_id=self.user_id)
        self.db.add(account)
        await self.db.flush()
        return account

    async def update_account(self, account_id: int, data: dict) -> Optional[VendorAccount]:
        account = await self.get_account(account_id)
        if not account:
            return None
        for key, val in data.items():
            if val is not None:
                setattr(account, key, val)
        await self.db.flush()
        return account

    async def delete_account(self, account_id: int) -> bool:
        account = await self.get_account(account_id)
        if not account:
            return False
        await self.db.delete(account)
        await self.db.flush()
        return True

    async def get_total(self) -> float:
        result = await self.db.execute(
            select(func.coalesce(func.sum(VendorAccount.amount), 0.0))
            .where(VendorAccount.user_id == self.user_id)
        )
        return float(result.scalar() or 0.0)

    async def get_cashflow_total(self) -> float:
        """Total of only vendor accounts included in cashflow."""
        result = await self.db.execute(
            select(func.coalesce(func.sum(VendorAccount.amount), 0.0))
            .where(
                VendorAccount.user_id == self.user_id,
                VendorAccount.included_in_cashflow == True,
            )
        )
        return float(result.scalar() or 0.0)
