"""Debug bills for user 1."""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(__file__))

async def main():
    from app.core.database import async_session_factory
    from sqlalchemy import text
    async with async_session_factory() as db:
        r = await db.execute(text(
            "SELECT user_id, COUNT(*), SUM(CASE WHEN is_active THEN 1 ELSE 0 END) as active "
            "FROM recurring_bills GROUP BY user_id"
        ))
        for row in r.fetchall():
            print(f"user_id={row[0]} total={row[1]} active={row[2]}")

        r = await db.execute(text(
            "SELECT id, name, is_active FROM recurring_bills WHERE user_id = 1 LIMIT 5"
        ))
        print("\nSample bills for user 1:")
        for row in r.fetchall():
            print(f"  id={row[0]} name={row[1]} active={row[2]}")

        # Check bill occurrences for user 1
        r = await db.execute(text(
            "SELECT COUNT(*) FROM bill_occurrences bo "
            "JOIN recurring_bills rb ON bo.recurring_bill_id = rb.id WHERE rb.user_id = 1"
        ))
        print(f"\nBill occurrences for user 1: {r.scalar()}")

asyncio.run(main())
