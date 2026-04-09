"""Quick debug script to check outstanding totals."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

async def main():
    from app.core.database import async_session_factory
    from sqlalchemy import text

    async with async_session_factory() as db:
        # First check enum values
        r = await db.execute(text(
            "SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid "
            "WHERE pg_type.typname = 'payablestatus'"
        ))
        payable_vals = [row[0] for row in r.fetchall()]
        print(f"PayableStatus enum values: {payable_vals}")

        r = await db.execute(text(
            "SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid "
            "WHERE pg_type.typname = 'billoccurrencestatus'"
        ))
        bill_vals = [row[0] for row in r.fetchall()]
        print(f"BillOccurrenceStatus enum values: {bill_vals}")

        # Check distinct statuses actually in the tables
        r = await db.execute(text("SELECT DISTINCT status::text FROM payables"))
        print(f"Distinct payable statuses in DB: {[row[0] for row in r.fetchall()]}")

        r = await db.execute(text("SELECT DISTINCT status::text FROM bill_occurrences"))
        print(f"Distinct bill_occurrence statuses in DB: {[row[0] for row in r.fetchall()]}")

        # Raw payables totals (no enum filter, just sum everything)
        r = await db.execute(text(
            "SELECT user_id, status::text, SUM(amount) as total, COUNT(*) as cnt "
            "FROM payables WHERE included_in_cashflow = true AND is_junked = false "
            "GROUP BY user_id, status"
        ))
        print("\nPayables by user and status:")
        for row in r.fetchall():
            print(f"  user={row[0]} status={row[1]} total=${row[2]:,.2f} count={row[3]}")

        # Bill occurrences totals
        r = await db.execute(text(
            "SELECT rb.user_id, bo.status::text, SUM(bo.amount) as total, COUNT(*) as cnt "
            "FROM bill_occurrences bo "
            "JOIN recurring_bills rb ON bo.recurring_bill_id = rb.id "
            "WHERE bo.included_in_cashflow = true "
            "GROUP BY rb.user_id, bo.status"
        ))
        print("\nBill occurrences by user and status:")
        for row in r.fetchall():
            print(f"  user={row[0]} status={row[1]} total=${row[2]:,.2f} count={row[3]}")

        # Permanent payables
        r = await db.execute(text(
            "SELECT user_id, SUM(amount) as total, COUNT(*) as cnt "
            "FROM payables WHERE included_in_cashflow = true AND is_junked = false "
            "AND is_permanent = true "
            "GROUP BY user_id"
        ))
        print("\nPermanent payables:")
        for row in r.fetchall():
            print(f"  user={row[0]} total=${row[1]:,.2f} count={row[2]}")

        # Top 10 largest payables
        r = await db.execute(text(
            "SELECT id, vendor_name, amount, status::text, is_permanent "
            "FROM payables WHERE included_in_cashflow = true AND is_junked = false "
            "ORDER BY amount DESC LIMIT 10"
        ))
        print("\nTop 10 largest payables:")
        for row in r.fetchall():
            print(f"  id={row[0]} vendor={row[1]} amount=${row[2]:,.2f} status={row[3]} permanent={row[4]}")

        # Top 10 largest bill occurrences
        r = await db.execute(text(
            "SELECT bo.id, rb.name, bo.amount, bo.status::text, bo.due_date "
            "FROM bill_occurrences bo "
            "JOIN recurring_bills rb ON bo.recurring_bill_id = rb.id "
            "WHERE bo.included_in_cashflow = true "
            "ORDER BY bo.amount DESC LIMIT 10"
        ))
        print("\nTop 10 largest bill occurrences:")
        for row in r.fetchall():
            print(f"  id={row[0]} name={row[1]} amount=${row[2]:,.2f} status={row[3]} due={row[4]}")

asyncio.run(main())
