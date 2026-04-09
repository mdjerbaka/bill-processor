"""Debug: show users and data counts per user."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

async def main():
    from app.core.database import async_session_factory
    from sqlalchemy import text

    async with async_session_factory() as db:
        r = await db.execute(text("SELECT id, username, created_at FROM users ORDER BY id"))
        print("=== USERS ===")
        for row in r.fetchall():
            print(f"  id={row[0]} username={row[1]} created={row[2]}")

        print()
        for table in ["payables", "recurring_bills", "invoices", "receivable_checks"]:
            r = await db.execute(text(f"SELECT user_id, COUNT(*) FROM {table} GROUP BY user_id"))
            rows = r.fetchall()
            print(f"{table}: {[(row[0], row[1]) for row in rows]}")

        print()
        r = await db.execute(text(
            "SELECT rb.user_id, COUNT(*) FROM bill_occurrences bo "
            "JOIN recurring_bills rb ON bo.recurring_bill_id = rb.id GROUP BY rb.user_id"
        ))
        print(f"bill_occurrences: {[(row[0], row[1]) for row in r.fetchall()]}")

        # Check if seed_bills.py was run
        r = await db.execute(text("SELECT id, name, user_id FROM recurring_bills ORDER BY id LIMIT 10"))
        print("\nFirst 10 recurring bills:")
        for row in r.fetchall():
            print(f"  id={row[0]} name={row[1]} user_id={row[2]}")

        # Check invoices sources
        r = await db.execute(text(
            "SELECT user_id, source, COUNT(*) FROM invoices GROUP BY user_id, source"
        ))
        print("\nInvoices by source:")
        for row in r.fetchall():
            print(f"  user_id={row[0]} source={row[1]} count={row[2]}")

asyncio.run(main())
