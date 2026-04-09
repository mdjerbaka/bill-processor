"""Clean up seed/test data for user_id=1 (markdjerbaka)."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

async def main():
    from app.core.database import async_session_factory
    from sqlalchemy import text

    async with async_session_factory() as db:
        # Delete bill occurrences for user 1's recurring bills
        r = await db.execute(text(
            "DELETE FROM bill_occurrences WHERE recurring_bill_id IN "
            "(SELECT id FROM recurring_bills WHERE user_id = 1)"
        ))
        print(f"Deleted {r.rowcount} bill_occurrences for user 1")

        # Delete recurring bills for user 1
        r = await db.execute(text("DELETE FROM recurring_bills WHERE user_id = 1"))
        print(f"Deleted {r.rowcount} recurring_bills for user 1")

        # Delete payables for user 1
        r = await db.execute(text("DELETE FROM payables WHERE user_id = 1"))
        print(f"Deleted {r.rowcount} payables for user 1")

        # Delete invoices for user 1 (should be 0)
        r = await db.execute(text("DELETE FROM invoices WHERE user_id = 1"))
        print(f"Deleted {r.rowcount} invoices for user 1")

        # Delete receivable_checks for user 1 (should be 0)
        r = await db.execute(text("DELETE FROM receivable_checks WHERE user_id = 1"))
        print(f"Deleted {r.rowcount} receivable_checks for user 1")

        await db.commit()
        print("\nDone! User 1 (markdjerbaka) data cleaned up.")

asyncio.run(main())
