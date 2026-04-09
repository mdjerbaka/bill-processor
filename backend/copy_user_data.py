"""Copy all data from user_id=2 (santimaw) to user_id=1 (markdjerbaka).

Uses INSERT INTO ... SELECT to copy all columns dynamically, swapping user_id.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


async def get_columns(db, table):
    """Get all column names for a table."""
    r = await db.execute(
        __import__("sqlalchemy", fromlist=["text"]).text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :t ORDER BY ordinal_position"
        ), {"t": table}
    )
    return [row[0] for row in r.fetchall()]


async def copy_table_simple(db, table, extra_where=""):
    """Copy rows from user_id=2 to user_id=1, replacing user_id and generating new id."""
    from sqlalchemy import text
    cols = await get_columns(db, table)
    # Columns to insert (skip 'id' — auto-generated)
    insert_cols = [c for c in cols if c != "id"]
    # Select expressions: swap user_id from 2 to 1
    select_exprs = ["1" if c == "user_id" else c for c in insert_cols]
    sql = (
        f"INSERT INTO {table} ({', '.join(insert_cols)}) "
        f"SELECT {', '.join(select_exprs)} FROM {table} WHERE user_id = 2 {extra_where} "
        f"RETURNING id"
    )
    r = await db.execute(text(sql))
    new_ids = [row[0] for row in r.fetchall()]
    print(f"Copied {len(new_ids)} {table}")
    return new_ids


async def main():
    from app.core.database import async_session_factory
    from sqlalchemy import text

    async with async_session_factory() as db:
        # Maps from old IDs to new IDs
        bill_map = {}
        payable_map = {}

        # 1. AppSettings — upsert
        cols = await get_columns(db, "app_settings")
        non_id_cols = [c for c in cols if c not in ("id", "user_id")]
        rows = (await db.execute(text("SELECT * FROM app_settings WHERE user_id = 2"))).fetchall()
        col_idx = {c: i for i, c in enumerate(cols)}
        for r in rows:
            key = r[col_idx["key"]]
            exists = (await db.execute(text(
                "SELECT id FROM app_settings WHERE user_id = 1 AND key = :k"
            ), {"k": key})).fetchone()
            if exists:
                sets = ", ".join(f"{c} = (SELECT {c} FROM app_settings WHERE id = :src_id)" for c in non_id_cols)
                await db.execute(text(
                    f"UPDATE app_settings SET {sets} WHERE id = :tgt_id"
                ), {"src_id": r[col_idx["id"]], "tgt_id": exists[0]})
            else:
                insert_cols = [c for c in cols if c != "id"]
                select_exprs = ["1" if c == "user_id" else c for c in insert_cols]
                await db.execute(text(
                    f"INSERT INTO app_settings ({', '.join(insert_cols)}) "
                    f"SELECT {', '.join(select_exprs)} FROM app_settings WHERE id = :src_id"
                ), {"src_id": r[col_idx["id"]]})
        print(f"Copied {len(rows)} app_settings")

        # 2. Simple tables (no outgoing FK dependencies besides user_id)
        await copy_table_simple(db, "receivable_checks")
        await copy_table_simple(db, "vendor_accounts")

        # 3. RecurringBills — need to map old_id -> new_id
        rb_cols = await get_columns(db, "recurring_bills")
        rb_non_id = [c for c in rb_cols if c != "id"]
        rb_select = ["1" if c == "user_id" else c for c in rb_non_id]
        old_bills = (await db.execute(text("SELECT id FROM recurring_bills WHERE user_id = 2 ORDER BY id"))).fetchall()
        r = await db.execute(text(
            f"INSERT INTO recurring_bills ({', '.join(rb_non_id)}) "
            f"SELECT {', '.join(rb_select)} FROM recurring_bills WHERE user_id = 2 ORDER BY id "
            f"RETURNING id"
        ))
        new_bill_ids = [row[0] for row in r.fetchall()]
        for old, new in zip(old_bills, new_bill_ids):
            bill_map[old[0]] = new
        print(f"Copied {len(new_bill_ids)} recurring_bills")

        # 4. BillOccurrences — swap recurring_bill_id, set matched_invoice_id to NULL
        bo_cols = await get_columns(db, "bill_occurrences")
        bo_non_id = [c for c in bo_cols if c != "id"]
        # We need to iterate per old recurring_bill to maintain mapping
        for old_rb_id, new_rb_id in bill_map.items():
            bo_select = []
            for c in bo_non_id:
                if c == "recurring_bill_id":
                    bo_select.append(str(new_rb_id))
                elif c == "matched_invoice_id":
                    bo_select.append("NULL")
                else:
                    bo_select.append(c)
            await db.execute(text(
                f"INSERT INTO bill_occurrences ({', '.join(bo_non_id)}) "
                f"SELECT {', '.join(bo_select)} FROM bill_occurrences WHERE recurring_bill_id = :old_id"
            ), {"old_id": old_rb_id})
        # Count total
        count = (await db.execute(text(
            "SELECT COUNT(*) FROM bill_occurrences bo JOIN recurring_bills rb ON bo.recurring_bill_id = rb.id WHERE rb.user_id = 1"
        ))).scalar()
        print(f"Copied bill_occurrences (total for user 1: {count})")

        # 5. Payables — need to map old_id -> new_id, set invoice_id to NULL
        p_cols = await get_columns(db, "payables")
        p_non_id = [c for c in p_cols if c != "id"]
        p_select = []
        for c in p_non_id:
            if c == "user_id":
                p_select.append("1")
            elif c == "invoice_id":
                p_select.append("NULL")
            else:
                p_select.append(c)
        old_payables = (await db.execute(text("SELECT id FROM payables WHERE user_id = 2 ORDER BY id"))).fetchall()
        r = await db.execute(text(
            f"INSERT INTO payables ({', '.join(p_non_id)}) "
            f"SELECT {', '.join(p_select)} FROM payables WHERE user_id = 2 ORDER BY id "
            f"RETURNING id"
        ))
        new_payable_ids = [row[0] for row in r.fetchall()]
        for old, new in zip(old_payables, new_payable_ids):
            payable_map[old[0]] = new
        print(f"Copied {len(new_payable_ids)} payables")

        # 6. PaymentsOut — swap payable_id using map
        po_cols = await get_columns(db, "payments_out")
        po_non_id = [c for c in po_cols if c != "id"]
        old_payments = (await db.execute(text("SELECT * FROM payments_out WHERE user_id = 2 ORDER BY id"))).fetchall()
        po_col_idx = {c: i for i, c in enumerate(po_cols)}
        for r in old_payments:
            vals = {}
            insert_parts = []
            for c in po_non_id:
                if c == "user_id":
                    insert_parts.append(f":p_{c}")
                    vals[f"p_{c}"] = 1
                elif c == "payable_id":
                    old_pid = r[po_col_idx[c]]
                    insert_parts.append(f":p_{c}")
                    vals[f"p_{c}"] = payable_map.get(old_pid) if old_pid else None
                else:
                    insert_parts.append(f":p_{c}")
                    vals[f"p_{c}"] = r[po_col_idx[c]]
            await db.execute(text(
                f"INSERT INTO payments_out ({', '.join(po_non_id)}) VALUES ({', '.join(insert_parts)})"
            ), vals)
        print(f"Copied {len(old_payments)} payments_out")

        # 7. Notifications — swap related_bill_id using map
        n_cols = await get_columns(db, "notifications")
        n_non_id = [c for c in n_cols if c != "id"]
        old_notifs = (await db.execute(text("SELECT * FROM notifications WHERE user_id = 2 ORDER BY id"))).fetchall()
        n_col_idx = {c: i for i, c in enumerate(n_cols)}
        for r in old_notifs:
            vals = {}
            insert_parts = []
            for c in n_non_id:
                if c == "user_id":
                    insert_parts.append(f":p_{c}")
                    vals[f"p_{c}"] = 1
                elif c == "related_bill_id":
                    old_bid = r[n_col_idx[c]]
                    insert_parts.append(f":p_{c}")
                    vals[f"p_{c}"] = bill_map.get(old_bid) if old_bid else None
                else:
                    insert_parts.append(f":p_{c}")
                    vals[f"p_{c}"] = r[n_col_idx[c]]
            await db.execute(text(
                f"INSERT INTO notifications ({', '.join(n_non_id)}) VALUES ({', '.join(insert_parts)})"
            ), vals)
        print(f"Copied {len(old_notifs)} notifications")

        await db.commit()
        print("\nDone! All santimaw data copied to markdjerbaka.")

asyncio.run(main())
