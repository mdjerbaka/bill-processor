"""Quick debug script to check outstanding totals."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

async def main():
    from app.core.database import async_session_factory
    from sqlalchemy import text

    async with async_session_factory() as db:
        # Payables outstanding
        r = await db.execute(text(
            "SELECT user_id, SUM(amount) as total, COUNT(*) as cnt "
            "FROM payables WHERE status IN ('outstanding', 'overdue') "
            "AND included_in_cashflow = true AND is_junked = false "
            "GROUP BY user_id"
        ))
        for row in r.fetchall():
            print(f"Payables user={row[0]}: total=${row[1]:,.2f} count={row[2]}")

        # Bill occurrences outstanding
        r = await db.execute(text(
            "SELECT rb.user_id, SUM(bo.amount) as total, COUNT(*) as cnt "
            "FROM bill_occurrences bo "
            "JOIN recurring_bills rb ON bo.recurring_bill_id = rb.id "
            "WHERE bo.status IN ('upcoming', 'due_soon', 'overdue') "
            "AND bo.included_in_cashflow = true "
            "GROUP BY rb.user_id"
        ))
        for row in r.fetchall():
            print(f"Bills user={row[0]}: total=${row[1]:,.2f} count={row[2]}")

        # Check if permanent payables are included
        r = await db.execute(text(
            "SELECT user_id, SUM(amount) as total, COUNT(*) as cnt "
            "FROM payables WHERE status IN ('outstanding', 'overdue') "
            "AND included_in_cashflow = true AND is_junked = false "
            "AND is_permanent = true "
            "GROUP BY user_id"
        ))
        for row in r.fetchall():
            print(f"Permanent payables user={row[0]}: total=${row[1]:,.2f} count={row[2]}")

        # Top 10 largest payables
        r = await db.execute(text(
            "SELECT id, vendor_name, amount, status, is_permanent "
            "FROM payables WHERE status IN ('outstanding', 'overdue') "
            "AND included_in_cashflow = true AND is_junked = false "
            "ORDER BY amount DESC LIMIT 10"
        ))
        print("\nTop 10 largest payables:")
        for row in r.fetchall():
            print(f"  id={row[0]} vendor={row[1]} amount=${row[2]:,.2f} status={row[3]} permanent={row[4]}")

        # Top 10 largest bill occurrences
        r = await db.execute(text(
            "SELECT bo.id, rb.name, bo.amount, bo.status, bo.due_date "
            "FROM bill_occurrences bo "
            "JOIN recurring_bills rb ON bo.recurring_bill_id = rb.id "
            "WHERE bo.status IN ('upcoming', 'due_soon', 'overdue') "
            "AND bo.included_in_cashflow = true "
            "ORDER BY bo.amount DESC LIMIT 10"
        ))
        print("\nTop 10 largest bill occurrences:")
        for row in r.fetchall():
            print(f"  id={row[0]} name={row[1]} amount=${row[2]:,.2f} status={row[3]} due={row[4]}")

asyncio.run(main())
