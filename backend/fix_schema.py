"""Fix missing custom_months column - migration was stamped but not applied."""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(__file__))

async def main():
    from app.core.database import async_session_factory
    from sqlalchemy import text
    async with async_session_factory() as db:
        # Check if column exists
        r = await db.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'recurring_bills' AND column_name = 'custom_months'"
        ))
        if r.fetchone():
            print("custom_months column already exists")
        else:
            await db.execute(text("ALTER TABLE recurring_bills ADD COLUMN custom_months JSON"))
            await db.commit()
            print("Added custom_months column to recurring_bills")

asyncio.run(main())
