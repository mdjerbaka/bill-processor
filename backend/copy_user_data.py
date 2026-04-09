"""Copy all data from user_id=2 (santimaw) to user_id=1 (markdjerbaka)."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

async def main():
    from app.core.database import async_session_factory
    from sqlalchemy import text

    async with async_session_factory() as db:
        # Maps from old IDs to new IDs
        bill_map = {}   # old recurring_bill_id -> new recurring_bill_id
        job_map = {}
        email_map = {}
        attachment_map = {}
        invoice_map = {}
        payable_map = {}

        # 1. AppSettings
        rows = (await db.execute(text(
            "SELECT key, value FROM app_settings WHERE user_id = 2"
        ))).fetchall()
        for r in rows:
            exists = (await db.execute(text(
                "SELECT id FROM app_settings WHERE user_id = 1 AND key = :k"
            ), {"k": r[0]})).fetchone()
            if exists:
                await db.execute(text(
                    "UPDATE app_settings SET value = :v WHERE user_id = 1 AND key = :k"
                ), {"v": r[1], "k": r[0]})
            else:
                await db.execute(text(
                    "INSERT INTO app_settings (key, value, user_id) VALUES (:k, :v, 1)"
                ), {"k": r[0], "v": r[1]})
        print(f"Copied {len(rows)} app_settings")

        # 2. ReceivableChecks
        rows = (await db.execute(text(
            "SELECT job_name, invoiced_amount, collect, notes, created_at FROM receivable_checks WHERE user_id = 2"
        ))).fetchall()
        for r in rows:
            await db.execute(text(
                "INSERT INTO receivable_checks (user_id, job_name, invoiced_amount, collect, notes, created_at) "
                "VALUES (1, :a, :b, :c, :d, :e)"
            ), {"a": r[0], "b": r[1], "c": r[2], "d": r[3], "e": r[4]})
        print(f"Copied {len(rows)} receivable_checks")

        # 3. Jobs
        rows = (await db.execute(text(
            "SELECT id, name, code, address, city, state, is_junked, junked_at, created_at FROM jobs WHERE user_id = 2"
        ))).fetchall()
        for r in rows:
            res = await db.execute(text(
                "INSERT INTO jobs (user_id, name, code, address, city, state, is_junked, junked_at, created_at) "
                "VALUES (1, :a, :b, :c, :d, :e, :f, :g, :h) RETURNING id"
            ), {"a": r[1], "b": r[2], "c": r[3], "d": r[4], "e": r[5], "f": r[6], "g": r[7], "h": r[8]})
            job_map[r[0]] = res.fetchone()[0]
        print(f"Copied {len(rows)} jobs")

        # 4. RecurringBills
        rows = (await db.execute(text(
            "SELECT id, name, vendor_name, amount, frequency, category, due_day, start_date, "
            "end_date, is_active, notes, vendor_account_number, custom_interval_days, credit_danger, created_at "
            "FROM recurring_bills WHERE user_id = 2"
        ))).fetchall()
        for r in rows:
            res = await db.execute(text(
                "INSERT INTO recurring_bills (user_id, name, vendor_name, amount, frequency, category, "
                "due_day, start_date, end_date, is_active, notes, vendor_account_number, "
                "custom_interval_days, credit_danger, created_at) "
                "VALUES (1, :a, :b, :c, :d, :e, :f, :g, :h, :i, :j, :k, :l, :m, :n) RETURNING id"
            ), {"a": r[1], "b": r[2], "c": r[3], "d": r[4], "e": r[5], "f": r[6],
                "g": r[7], "h": r[8], "i": r[9], "j": r[10], "k": r[11], "l": r[12], "m": r[13], "n": r[14]})
            bill_map[r[0]] = res.fetchone()[0]
        print(f"Copied {len(rows)} recurring_bills")

        # 5. VendorAccounts
        rows = (await db.execute(text(
            "SELECT vendor_name, amount, created_at FROM vendor_accounts WHERE user_id = 2"
        ))).fetchall()
        for r in rows:
            await db.execute(text(
                "INSERT INTO vendor_accounts (user_id, vendor_name, amount, created_at) "
                "VALUES (1, :a, :b, :c)"
            ), {"a": r[0], "b": r[1], "c": r[2]})
        print(f"Copied {len(rows)} vendor_accounts")

        # 6. BillOccurrences (no user_id, references recurring_bills)
        rows = (await db.execute(text(
            "SELECT recurring_bill_id, due_date, amount, status, paid_at, included_in_cashflow, "
            "matched_invoice_id, created_at "
            "FROM bill_occurrences bo "
            "JOIN recurring_bills rb ON bo.recurring_bill_id = rb.id "
            "WHERE rb.user_id = 2"
        ))).fetchall()
        for r in rows:
            new_bill_id = bill_map.get(r[0])
            if new_bill_id:
                await db.execute(text(
                    "INSERT INTO bill_occurrences (recurring_bill_id, due_date, amount, status, "
                    "paid_at, included_in_cashflow, matched_invoice_id, created_at) "
                    "VALUES (:a, :b, :c, :d, :e, :f, NULL, :h)"
                ), {"a": new_bill_id, "b": r[1], "c": r[2], "d": r[3], "e": r[4], "f": r[5], "h": r[7]})
        print(f"Copied {len(rows)} bill_occurrences")

        # 7. Payables (with or without invoice_id)
        rows = (await db.execute(text(
            "SELECT id, invoice_id, vendor_name, invoice_number, amount, due_date, status, "
            "is_permanent, included_in_cashflow, is_junked, junked_at, qbo_bill_id, "
            "job_name, paid_at, created_at "
            "FROM payables WHERE user_id = 2"
        ))).fetchall()
        for r in rows:
            res = await db.execute(text(
                "INSERT INTO payables (user_id, invoice_id, vendor_name, invoice_number, amount, "
                "due_date, status, is_permanent, included_in_cashflow, is_junked, junked_at, "
                "qbo_bill_id, job_name, paid_at, created_at) "
                "VALUES (1, NULL, :b, :c, :d, :e, :f, :g, :h, :i, :j, :k, :l, :m, :n) RETURNING id"
            ), {"b": r[2], "c": r[3], "d": r[4], "e": r[5], "f": r[6], "g": r[7],
                "h": r[8], "i": r[9], "j": r[10], "k": r[11], "l": r[12], "m": r[13], "n": r[14]})
            payable_map[r[0]] = res.fetchone()[0]
        print(f"Copied {len(rows)} payables")

        # 8. PaymentsOut
        rows = (await db.execute(text(
            "SELECT payable_id, vendor_name, amount, check_number, payment_date, "
            "is_cleared, cleared_at, notes, created_at "
            "FROM payments_out WHERE user_id = 2"
        ))).fetchall()
        for r in rows:
            new_payable_id = payable_map.get(r[0]) if r[0] else None
            await db.execute(text(
                "INSERT INTO payments_out (user_id, payable_id, vendor_name, amount, check_number, "
                "payment_date, is_cleared, cleared_at, notes, created_at) "
                "VALUES (1, :a, :b, :c, :d, :e, :f, :g, :h, :i)"
            ), {"a": new_payable_id, "b": r[1], "c": r[2], "d": r[3], "e": r[4],
                "f": r[5], "g": r[6], "h": r[7], "i": r[8]})
        print(f"Copied {len(rows)} payments_out")

        # 9. Notifications (references recurring_bills)
        rows = (await db.execute(text(
            "SELECT type, related_bill_id, message, is_read, created_at "
            "FROM notifications WHERE user_id = 2"
        ))).fetchall()
        for r in rows:
            new_bill_id = bill_map.get(r[1]) if r[1] else None
            await db.execute(text(
                "INSERT INTO notifications (user_id, type, related_bill_id, message, is_read, created_at) "
                "VALUES (1, :a, :b, :c, :d, :e)"
            ), {"a": r[0], "b": new_bill_id, "c": r[2], "d": r[3], "e": r[4]})
        print(f"Copied {len(rows)} notifications")

        await db.commit()
        print("\nDone! All santimaw data copied to markdjerbaka.")

asyncio.run(main())
