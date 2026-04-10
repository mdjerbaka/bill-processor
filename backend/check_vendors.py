"""Check vendor accounts data."""
import asyncio
from app.core.database import async_session_factory
from app.models.models import VendorAccount
from sqlalchemy import select

async def main():
    async with async_session_factory() as db:
        result = await db.execute(select(VendorAccount).where(VendorAccount.user_id == 2))
        for v in result.scalars().all():
            print(f"  ID={v.id} name={v.vendor_name} cashflow={v.included_in_cashflow}")

asyncio.run(main())
