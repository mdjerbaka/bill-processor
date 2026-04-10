"""Quick script to list users."""
import asyncio
from app.core.database import async_session
from app.models.models import User
from sqlalchemy import select

async def main():
    async with async_session() as db:
        result = await db.execute(select(User))
        for u in result.scalars().all():
            print(f"ID={u.id} email={u.email} company={getattr(u, 'company_name', 'N/A')}")

asyncio.run(main())
