"""Remove duplicate RecurringBill rows for the santimaw user.

Duplicates are defined as rows with identical:
  (name, vendor_name, amount, frequency, due_day_of_month, due_month)

For each group of duplicates we keep the OLDEST row (smallest id) and:
  - Re-parent any BillOccurrence rows from dupes to the keeper, deduplicating
    by (recurring_bill_id, due_date) on the way.
  - Re-parent any Notification rows from dupes to the keeper.
  - Delete the duplicate RecurringBill rows.

Run on the server:
    docker compose exec backend python /app/dedupe_santimaw_bills.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import defaultdict

from sqlalchemy import delete, select, update

from app.core.database import async_session_factory
from app.models.models import (
    BillOccurrence,
    Notification,
    RecurringBill,
    User,
)


SANTIMAW_HINT = "santimaw"


def _key(bill: RecurringBill) -> tuple:
    return (
        (bill.name or "").strip().lower(),
        (bill.vendor_name or "").strip().lower(),
        round(float(bill.amount or 0), 2),
        bill.frequency.value if bill.frequency else None,
        bill.due_day_of_month,
        bill.due_month,
    )


async def main(dry_run: bool) -> int:
    async with async_session_factory() as db:
        # Find santimaw user(s)
        users = (await db.execute(
            select(User).where(User.username.ilike(f"%{SANTIMAW_HINT}%"))
        )).scalars().all()
        if not users:
            print(f"No user matched '{SANTIMAW_HINT}'. Existing users:")
            all_users = (await db.execute(select(User))).scalars().all()
            for u in all_users:
                print(f"  id={u.id} username={u.username}")
            return 1

        for user in users:
            print(f"\n=== User id={user.id} username={user.username} ===")

            bills = (await db.execute(
                select(RecurringBill).where(RecurringBill.user_id == user.id)
            )).scalars().all()
            print(f"Total recurring bills: {len(bills)}")

            groups: dict[tuple, list[RecurringBill]] = defaultdict(list)
            for b in bills:
                groups[_key(b)].append(b)

            dupe_groups = {k: sorted(v, key=lambda b: b.id) for k, v in groups.items() if len(v) > 1}
            if not dupe_groups:
                print("No duplicates found.")
                continue

            total_to_delete = sum(len(v) - 1 for v in dupe_groups.values())
            print(f"Duplicate groups: {len(dupe_groups)}, rows to remove: {total_to_delete}")

            for key, dupes in dupe_groups.items():
                keeper = dupes[0]
                losers = dupes[1:]
                print(
                    f"  KEEP id={keeper.id} '{keeper.name}' (${keeper.amount}) "
                    f"-> remove {[b.id for b in losers]}"
                )

                if dry_run:
                    continue

                loser_ids = [b.id for b in losers]

                # Move occurrences: keep one per due_date on the keeper.
                keeper_dates = {
                    o.due_date for o in (await db.execute(
                        select(BillOccurrence).where(
                            BillOccurrence.recurring_bill_id == keeper.id
                        )
                    )).scalars().all()
                }
                loser_occs = (await db.execute(
                    select(BillOccurrence).where(
                        BillOccurrence.recurring_bill_id.in_(loser_ids)
                    )
                )).scalars().all()
                for occ in loser_occs:
                    if occ.due_date in keeper_dates:
                        await db.delete(occ)
                    else:
                        occ.recurring_bill_id = keeper.id
                        keeper_dates.add(occ.due_date)

                # Re-parent notifications
                await db.execute(
                    update(Notification)
                    .where(Notification.related_bill_id.in_(loser_ids))
                    .values(related_bill_id=keeper.id)
                )

                # Delete duplicate RecurringBill rows
                await db.execute(
                    delete(RecurringBill).where(RecurringBill.id.in_(loser_ids))
                )

            if dry_run:
                print("(dry-run: no changes committed)")
                await db.rollback()
            else:
                await db.commit()
                print("Changes committed.")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.dry_run)))
