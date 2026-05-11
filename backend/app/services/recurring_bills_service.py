"""Recurring bills management and cash flow calculations."""

from __future__ import annotations

import calendar
import logging
from datetime import datetime, timedelta, timezone, date
from typing import Optional

from sqlalchemy import select, func, and_, or_, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.models import (
    AppSetting,
    BillCategory,
    BillFrequency,
    BillOccurrence,
    Invoice,
    Notification,
    OccurrenceStatus,
    Payable,
    PayableStatus,
    ReceivableCheck,
    RecurringBill,
)

logger = logging.getLogger(__name__)


def _compute_next_due_date(
    frequency: BillFrequency,
    due_day: Optional[int],
    due_month: Optional[int] = None,
    after: Optional[datetime] = None,
    custom_months: Optional[list[int]] = None,
) -> datetime:
    """Compute the next due date for a recurring bill based on frequency."""
    now = after or datetime.now(timezone.utc)
    today = now.date()

    def _safe_date(year: int, month: int, day: int) -> date:
        """Clamp day to the last day of the given month."""
        max_day = calendar.monthrange(year, month)[1]
        return date(year, month, min(day, max_day))

    if frequency == BillFrequency.WEEKLY:
        # Next occurrence is simply the next day from today (every 7 days)
        candidate = today + timedelta(days=1)
        return datetime(candidate.year, candidate.month, candidate.day, tzinfo=timezone.utc)

    if frequency == BillFrequency.MONTHLY:
        candidate = _safe_date(today.year, today.month, due_day)
        if candidate <= today:
            month = today.month + 1
            year = today.year
            if month > 12:
                month = 1
                year += 1
            candidate = _safe_date(year, month, due_day)
        return datetime(candidate.year, candidate.month, candidate.day, tzinfo=timezone.utc)

    if frequency == BillFrequency.QUARTERLY:
        # Due months: due_month, due_month+3, due_month+6, due_month+9
        base_month = due_month or 1
        quarter_months = sorted(set((base_month + i * 3 - 1) % 12 + 1 for i in range(4)))
        for year_offset in range(2):
            y = today.year + year_offset
            for m in quarter_months:
                candidate = _safe_date(y, m, due_day)
                if candidate > today:
                    return datetime(candidate.year, candidate.month, candidate.day, tzinfo=timezone.utc)
        # Fallback: next year's first quarter month
        return datetime(today.year + 2, quarter_months[0], due_day, tzinfo=timezone.utc)

    if frequency == BillFrequency.SEMI_ANNUAL:
        base_month = due_month or 1
        semi_months = sorted(set((base_month + i * 6 - 1) % 12 + 1 for i in range(2)))
        for year_offset in range(2):
            y = today.year + year_offset
            for m in semi_months:
                candidate = _safe_date(y, m, due_day)
                if candidate > today:
                    return datetime(candidate.year, candidate.month, candidate.day, tzinfo=timezone.utc)
        return datetime(today.year + 2, semi_months[0], due_day, tzinfo=timezone.utc)

    if frequency == BillFrequency.ANNUAL:
        month = due_month or 1
        candidate = _safe_date(today.year, month, due_day)
        if candidate <= today:
            candidate = _safe_date(today.year + 1, month, due_day)
        return datetime(candidate.year, candidate.month, candidate.day, tzinfo=timezone.utc)

    if frequency == BillFrequency.BIENNIAL:
        month = due_month or 1
        candidate = _safe_date(today.year, month, due_day)
        if candidate <= today:
            candidate = _safe_date(today.year + 2, month, due_day)
        return datetime(candidate.year, candidate.month, candidate.day, tzinfo=timezone.utc)

    if frequency == BillFrequency.CUSTOM:
        months = sorted(custom_months or [])
        if not months:
            return datetime(today.year, today.month, due_day or 1, tzinfo=timezone.utc)
        for year_offset in range(3):
            y = today.year + year_offset
            for m in months:
                candidate = _safe_date(y, m, due_day or 1)
                if candidate > today:
                    return datetime(candidate.year, candidate.month, candidate.day, tzinfo=timezone.utc)
        return datetime(today.year + 3, months[0], due_day or 1, tzinfo=timezone.utc)

    # Default fallback
    return datetime(today.year, today.month, due_day, tzinfo=timezone.utc)


def _generate_dates_in_range(
    frequency: BillFrequency,
    due_day: Optional[int],
    due_month: Optional[int],
    start: date,
    end: date,
    custom_months: Optional[list[int]] = None,
) -> list[date]:
    """Generate all occurrence dates within [start, end] for the given frequency."""
    dates = []

    def _safe_date(year: int, month: int, day: int) -> date:
        max_day = calendar.monthrange(year, month)[1]
        return date(year, month, min(day, max_day))

    # Per-frequency anchor for "this period". We look backward to the
    # start of the current period so a bill whose due-day already passed
    # in the current period still gets an occurrence row generated (and
    # can therefore be flagged OVERDUE). Without this, a monthly bill
    # due on the 5th would be skipped if today is the 6th, vanishing
    # from the current-month view.
    if frequency == BillFrequency.MONTHLY:
        period_start = date(start.year, start.month, 1)
    elif frequency == BillFrequency.QUARTERLY:
        # First month of the current calendar quarter
        q_first = ((start.month - 1) // 3) * 3 + 1
        period_start = date(start.year, q_first, 1)
    elif frequency == BillFrequency.SEMI_ANNUAL:
        period_start = date(start.year, 1 if start.month <= 6 else 7, 1)
    elif frequency == BillFrequency.ANNUAL:
        period_start = date(start.year, 1, 1)
    elif frequency == BillFrequency.BIENNIAL:
        period_start = date(start.year - (start.year % 2), 1, 1)
    elif frequency == BillFrequency.CUSTOM:
        period_start = date(start.year, 1, 1)
    else:
        period_start = start

    if frequency == BillFrequency.WEEKLY:
        # Generate one occurrence per week starting from start
        current = start
        while current <= end:
            dates.append(current)
            current += timedelta(days=7)
        return dates

    if frequency == BillFrequency.MONTHLY:
        current = period_start
        while current <= end:
            candidate = _safe_date(current.year, current.month, due_day)
            if period_start <= candidate <= end:
                dates.append(candidate)
            # advance month
            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)

    elif frequency == BillFrequency.QUARTERLY:
        base_month = due_month or 1
        quarter_months = sorted(set((base_month + i * 3 - 1) % 12 + 1 for i in range(4)))
        for year in range(period_start.year, end.year + 1):
            for m in quarter_months:
                candidate = _safe_date(year, m, due_day)
                if period_start <= candidate <= end:
                    dates.append(candidate)

    elif frequency == BillFrequency.SEMI_ANNUAL:
        base_month = due_month or 1
        semi_months = sorted(set((base_month + i * 6 - 1) % 12 + 1 for i in range(2)))
        for year in range(period_start.year, end.year + 1):
            for m in semi_months:
                candidate = _safe_date(year, m, due_day)
                if period_start <= candidate <= end:
                    dates.append(candidate)

    elif frequency == BillFrequency.ANNUAL:
        month = due_month or 1
        for year in range(period_start.year, end.year + 1):
            candidate = _safe_date(year, month, due_day)
            if period_start <= candidate <= end:
                dates.append(candidate)

    elif frequency == BillFrequency.BIENNIAL:
        month = due_month or 1
        for year in range(period_start.year, end.year + 2, 2):
            candidate = _safe_date(year, month, due_day)
            if period_start <= candidate <= end:
                dates.append(candidate)

    elif frequency == BillFrequency.CUSTOM:
        months = sorted(custom_months or [])
        for year in range(period_start.year, end.year + 1):
            for m in months:
                candidate = _safe_date(year, m, due_day or 1)
                if period_start <= candidate <= end:
                    dates.append(candidate)

    return dates


class RecurringBillsService:
    """Manages recurring bills and their occurrences."""

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id

    # ── CRUD ─────────────────────────────────────────────

    async def create_bill(self, data: dict) -> RecurringBill:
        """Create a new recurring bill and compute its next due date."""
        freq = BillFrequency(data["frequency"])
        cat = BillCategory(data.get("category", "other"))

        bill = RecurringBill(
            name=data["name"],
            vendor_name=data["vendor_name"],
            amount=data["amount"],
            frequency=freq,
            due_day_of_month=data["due_day_of_month"],
            due_month=data.get("due_month"),
            custom_months=data.get("custom_months"),
            category=cat,
            notes=data.get("notes"),
            is_auto_pay=data.get("is_auto_pay", False),
            alert_days_before=data.get("alert_days_before", 7),
            user_id=self.user_id,
        )
        bill.next_due_date = _compute_next_due_date(
            freq, bill.due_day_of_month, bill.due_month, custom_months=bill.custom_months
        )
        self.db.add(bill)
        await self.db.flush()
        return bill

    async def update_bill(self, bill_id: int, data: dict) -> Optional[RecurringBill]:
        """Update a recurring bill."""
        result = await self.db.execute(
            select(RecurringBill).where(RecurringBill.id == bill_id, RecurringBill.user_id == self.user_id)
        )
        bill = result.scalar_one_or_none()
        if not bill:
            return None

        for key, value in data.items():
            if value is not None and hasattr(bill, key):
                if key == "frequency":
                    setattr(bill, key, BillFrequency(value))
                elif key == "category":
                    setattr(bill, key, BillCategory(value))
                else:
                    setattr(bill, key, value)

        # If included_in_cashflow changed, propagate to upcoming/due_soon occurrences
        if "included_in_cashflow" in data and data["included_in_cashflow"] is not None:
            await self.db.execute(
                update(BillOccurrence)
                .where(
                    BillOccurrence.recurring_bill_id == bill_id,
                    BillOccurrence.status.in_([OccurrenceStatus.UPCOMING, OccurrenceStatus.DUE_SOON]),
                )
                .values(included_in_cashflow=data["included_in_cashflow"])
            )

        # Recompute next due date
        bill.next_due_date = _compute_next_due_date(
            bill.frequency, bill.due_day_of_month, bill.due_month, custom_months=bill.custom_months
        )
        await self.db.flush()
        return bill

    async def delete_bill(self, bill_id: int) -> bool:
        """Hard-delete a recurring bill and all its occurrences and notifications."""
        result = await self.db.execute(
            select(RecurringBill).where(RecurringBill.id == bill_id, RecurringBill.user_id == self.user_id)
        )
        bill = result.scalar_one_or_none()
        if not bill:
            return False
        # Delete related notifications
        await self.db.execute(
            delete(Notification).where(Notification.related_bill_id == bill_id)
        )
        # Delete all occurrences
        await self.db.execute(
            delete(BillOccurrence).where(BillOccurrence.recurring_bill_id == bill_id)
        )
        # Delete the bill itself
        await self.db.execute(
            delete(RecurringBill).where(RecurringBill.id == bill_id)
        )
        await self.db.flush()
        return True

    async def get_bill(self, bill_id: int) -> Optional[RecurringBill]:
        """Get a single recurring bill by ID."""
        result = await self.db.execute(
            select(RecurringBill).where(RecurringBill.id == bill_id, RecurringBill.user_id == self.user_id)
        )
        return result.scalar_one_or_none()

    async def list_bills(self, include_inactive: bool = False) -> list[RecurringBill]:
        """List all recurring bills."""
        q = select(RecurringBill).where(RecurringBill.user_id == self.user_id).order_by(RecurringBill.next_due_date.asc())
        if not include_inactive:
            q = q.where(RecurringBill.is_active == True)  # noqa: E712
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def toggle_active(self, bill_id: int) -> Optional[RecurringBill]:
        """Flip is_active on a recurring bill (pause/resume)."""
        bill = await self.get_bill(bill_id)
        if not bill:
            return None
        bill.is_active = not bool(bill.is_active)
        await self.db.flush()
        return bill

    # ── Occurrence Generation ────────────────────────────

    async def generate_occurrences(self, days_ahead: int = 60) -> int:
        """Generate BillOccurrence records for the next N days for all active bills."""
        now = datetime.now(timezone.utc)
        today = now.date()
        end_date = today + timedelta(days=days_ahead)

        bills = await self.list_bills()
        created_count = 0

        for bill in bills:
            dates = _generate_dates_in_range(
                bill.frequency, bill.due_day_of_month, bill.due_month, today, end_date,
                custom_months=bill.custom_months,
            )
            for d in dates:
                due_dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
                # Check if occurrence already exists
                existing = await self.db.execute(
                    select(BillOccurrence).where(
                        BillOccurrence.recurring_bill_id == bill.id,
                        BillOccurrence.due_date == due_dt,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                occ = BillOccurrence(
                    recurring_bill_id=bill.id,
                    due_date=due_dt,
                    amount=bill.amount,
                    status=OccurrenceStatus.UPCOMING,
                    included_in_cashflow=bill.included_in_cashflow,
                )
                self.db.add(occ)
                created_count += 1

            # Update next_due_date on the bill
            bill.next_due_date = _compute_next_due_date(
                bill.frequency, bill.due_day_of_month, bill.due_month, custom_months=bill.custom_months
            )

        await self.db.flush()
        return created_count

    async def check_overdue(self) -> int:
        """Mark occurrences as OVERDUE if past due and not skipped."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(BillOccurrence).where(
                BillOccurrence.due_date < now,
                BillOccurrence.status.in_([
                    OccurrenceStatus.UPCOMING,
                    OccurrenceStatus.DUE_SOON,
                ]),
            )
        )
        # Note: PAID and SKIPPED occurrences are excluded since they aren't in the .in_ list
        occurrences = result.scalars().all()
        for occ in occurrences:
            occ.status = OccurrenceStatus.OVERDUE
        await self.db.flush()
        return len(occurrences)

    async def check_due_soon(self) -> int:
        """Mark occurrences as DUE_SOON if within alert window."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(BillOccurrence)
            .join(RecurringBill)
            .options(joinedload(BillOccurrence.recurring_bill))
            .where(
                BillOccurrence.status == OccurrenceStatus.UPCOMING,
                BillOccurrence.due_date > now,
                BillOccurrence.due_date <= now + timedelta(days=30),
            )
        )
        occurrences = result.unique().scalars().all()
        updated = 0
        for occ in occurrences:
            bill = occ.recurring_bill
            if bill and occ.due_date <= now + timedelta(days=bill.alert_days_before):
                occ.status = OccurrenceStatus.DUE_SOON
                updated += 1
        await self.db.flush()
        return updated

    async def auto_pay_due_occurrences(self) -> int:
        """Auto-pay occurrences whose parent bill has is_auto_pay=True and are due or overdue."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(BillOccurrence)
            .join(RecurringBill)
            .where(
                RecurringBill.user_id == self.user_id,
                RecurringBill.is_auto_pay == True,  # noqa: E712
                BillOccurrence.due_date <= now,
                BillOccurrence.status.in_([
                    OccurrenceStatus.UPCOMING,
                    OccurrenceStatus.DUE_SOON,
                    OccurrenceStatus.OVERDUE,
                ]),
            )
        )
        occurrences = result.scalars().all()
        for occ in occurrences:
            occ.status = OccurrenceStatus.PAID
            occ.paid_at = now
            occ.included_in_cashflow = False
        await self.db.flush()
        return len(occurrences)

    async def skip_occurrence(self, occurrence_id: int) -> Optional[BillOccurrence]:
        """Skip a bill occurrence."""
        result = await self.db.execute(
            select(BillOccurrence)
            .join(RecurringBill)
            .where(BillOccurrence.id == occurrence_id, RecurringBill.user_id == self.user_id)
        )
        occ = result.scalar_one_or_none()
        if occ:
            occ.status = OccurrenceStatus.SKIPPED
            await self.db.flush()
        return occ

    async def mark_paid(self, occurrence_id: int) -> Optional[BillOccurrence]:
        """Mark a bill occurrence as paid (local tracking only, not synced to QB)."""
        result = await self.db.execute(
            select(BillOccurrence)
            .join(RecurringBill)
            .options(joinedload(BillOccurrence.recurring_bill))
            .where(BillOccurrence.id == occurrence_id, RecurringBill.user_id == self.user_id)
        )
        occ = result.unique().scalar_one_or_none()
        if occ:
            occ.status = OccurrenceStatus.PAID
            occ.paid_at = datetime.now(timezone.utc)
            occ.included_in_cashflow = False
            await self.db.flush()
        return occ

    async def toggle_cashflow(self, occurrence_id: int) -> Optional[BillOccurrence]:
        """Toggle whether an occurrence is included in cash flow calculations."""
        result = await self.db.execute(
            select(BillOccurrence)
            .join(RecurringBill)
            .where(BillOccurrence.id == occurrence_id, RecurringBill.user_id == self.user_id)
        )
        occ = result.scalar_one_or_none()
        if occ:
            occ.included_in_cashflow = not occ.included_in_cashflow
            await self.db.flush()
        return occ

    async def bulk_delete_occurrences(self, ids: list[int]) -> int:
        """Delete only the selected occurrences (leaves parent recurring bills intact).

        This used to also delete the parent recurring bill and all sibling
        occurrences, which caused the original bill to disappear when a user
        deleted a duplicate. Now we only remove the rows the user selected.
        """
        if not ids:
            return 0

        # Restrict to occurrences owned by this user
        owned_result = await self.db.execute(
            select(BillOccurrence.id)
            .join(RecurringBill)
            .where(BillOccurrence.id.in_(ids), RecurringBill.user_id == self.user_id)
        )
        owned_ids = [row[0] for row in owned_result.all()]
        if not owned_ids:
            return 0

        await self.db.execute(
            delete(BillOccurrence).where(BillOccurrence.id.in_(owned_ids))
        )
        await self.db.flush()
        return len(owned_ids)

    async def auto_match_invoice(self, invoice: Invoice) -> Optional[BillOccurrence]:
        """Try to match an incoming invoice to an unpaid recurring bill occurrence.

        Matching logic:
        - Vendor name: case-insensitive substring match (invoice vendor
          contains the recurring bill vendor name or vice versa)
        - Date window: occurrence due_date within ±15 days of today
        - Picks the nearest unpaid occurrence by due_date
        - Updates the occurrence amount to the actual invoice total
        - Records the invoice_id for audit trail
        """
        if not invoice.vendor_name:
            return None

        vendor = invoice.vendor_name.strip().lower()
        if not vendor:
            return None

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=15)
        window_end = now + timedelta(days=15)

        # Find active recurring bills with matching vendor name
        result = await self.db.execute(
            select(RecurringBill).where(
                RecurringBill.is_active == True,  # noqa: E712
                RecurringBill.user_id == self.user_id,
            )
        )
        bills = result.scalars().all()

        matching_bill_ids = []
        for bill in bills:
            bill_vendor = bill.vendor_name.strip().lower()
            # Substring match in either direction
            if bill_vendor in vendor or vendor in bill_vendor:
                matching_bill_ids.append(bill.id)

        if not matching_bill_ids:
            return None

        # Find the nearest unpaid occurrence within the date window
        result = await self.db.execute(
            select(BillOccurrence)
            .where(
                BillOccurrence.recurring_bill_id.in_(matching_bill_ids),
                BillOccurrence.status.in_([
                    OccurrenceStatus.UPCOMING,
                    OccurrenceStatus.DUE_SOON,
                    OccurrenceStatus.OVERDUE,
                ]),
                BillOccurrence.due_date >= window_start,
                BillOccurrence.due_date <= window_end,
            )
            .order_by(
                func.abs(func.extract("epoch", BillOccurrence.due_date - now))
            )
            .limit(1)
        )
        occ = result.scalar_one_or_none()
        if not occ:
            return None

        # Mark paid and update with actual invoice data
        occ.status = OccurrenceStatus.PAID
        occ.paid_at = datetime.now(timezone.utc)
        occ.matched_invoice_id = invoice.id
        if invoice.total_amount:
            occ.amount = invoice.total_amount
        await self.db.flush()

        logger.info(
            f"Auto-matched invoice {invoice.id} (vendor={invoice.vendor_name}) "
            f"to occurrence {occ.id} (bill_id={occ.recurring_bill_id}, due={occ.due_date.date()})"
        )
        return occ

    # ── Query ────────────────────────────────────────────

    async def list_occurrences(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
    ) -> list[dict]:
        """List bill occurrences with optional filters, enriched with bill data."""
        q = (
            select(BillOccurrence)
            .join(RecurringBill)
            .options(joinedload(BillOccurrence.recurring_bill))
            .where(
                RecurringBill.is_active == True,  # noqa: E712
                RecurringBill.user_id == self.user_id,
            )
            .order_by(BillOccurrence.due_date.asc())
        )
        if start_date:
            q = q.where(BillOccurrence.due_date >= start_date)
        if end_date:
            q = q.where(BillOccurrence.due_date <= end_date)
        if status:
            q = q.where(BillOccurrence.status == OccurrenceStatus(status))
        if category:
            q = q.where(RecurringBill.category == BillCategory(category))

        result = await self.db.execute(q)
        occurrences = result.unique().scalars().all()

        now_date = datetime.now(timezone.utc).date()
        enriched = []
        for occ in occurrences:
            bill = occ.recurring_bill
            days_overdue = None
            if occ.status == OccurrenceStatus.OVERDUE:
                days_overdue = (now_date - occ.due_date.date()).days
            enriched.append({
                "id": occ.id,
                "recurring_bill_id": occ.recurring_bill_id,
                "due_date": occ.due_date,
                "amount": occ.amount,
                "status": occ.status.value,
                "notes": occ.notes,
                "bill_name": bill.name if bill else None,
                "vendor_name": bill.vendor_name if bill else None,
                "category": bill.category.value if bill else None,
                "is_auto_pay": bill.is_auto_pay if bill else None,
                "paid_at": occ.paid_at,
                "matched_invoice_id": occ.matched_invoice_id,
                "days_overdue": days_overdue,
                "included_in_cashflow": occ.included_in_cashflow,
                "created_at": occ.created_at,
            })
        return enriched

    # ── Master List (derived per-bill view) ──────────────

    async def get_master_list(self, include_inactive: bool = False) -> list[dict]:
        """Return one row per recurring bill with derived status.

        Used by the "Master List" UI so the client never has to think in
        terms of per-period occurrence rows: each bill shows its
        next due date, last paid date, and a tiered late flag.

        If `include_inactive` is True, paused bills are included with
        their `is_active` flag set to False (so the UI can grey them out).
        """
        bills = await self.list_bills(include_inactive=include_inactive)
        if not bills:
            return []

        now = datetime.now(timezone.utc)
        today = now.date()

        # Pull all occurrences for these bills in one query
        bill_ids = [b.id for b in bills]
        occ_result = await self.db.execute(
            select(BillOccurrence)
            .where(BillOccurrence.recurring_bill_id.in_(bill_ids))
            .order_by(BillOccurrence.due_date.asc())
        )
        all_occs = list(occ_result.scalars().all())

        # Index by bill
        by_bill: dict[int, list[BillOccurrence]] = {}
        for occ in all_occs:
            by_bill.setdefault(occ.recurring_bill_id, []).append(occ)

        items: list[dict] = []
        for bill in bills:
            occs = by_bill.get(bill.id, [])

            # Last paid: max paid_at across PAID occurrences
            paid_occs = [o for o in occs if o.status == OccurrenceStatus.PAID and o.paid_at]
            last_paid_at = max((o.paid_at for o in paid_occs), default=None)

            # Pick the "current" occurrence: prefer the earliest unpaid
            # (overdue/due_soon/upcoming). If none exists, fall back to
            # the most recent paid one (so the row still shows "paid").
            unpaid = [
                o for o in occs
                if o.status in (
                    OccurrenceStatus.OVERDUE,
                    OccurrenceStatus.DUE_SOON,
                    OccurrenceStatus.UPCOMING,
                )
            ]
            current = unpaid[0] if unpaid else (paid_occs[-1] if paid_occs else None)

            current_status = "upcoming"
            current_occ_id: Optional[int] = None
            days_overdue: Optional[int] = None
            days_until_due: Optional[int] = None
            late_tier = "none"

            if current is not None:
                current_occ_id = current.id
                current_status = current.status.value
                if current.status == OccurrenceStatus.OVERDUE:
                    days_overdue = (today - current.due_date.date()).days
                    if days_overdue >= 25:
                        late_tier = "red"
                    elif days_overdue >= 8:
                        late_tier = "orange"
                    elif days_overdue >= 1:
                        late_tier = "yellow"
                elif current.status in (OccurrenceStatus.UPCOMING, OccurrenceStatus.DUE_SOON):
                    days_until_due = (current.due_date.date() - today).days

            items.append({
                "id": bill.id,
                "name": bill.name,
                "vendor_name": bill.vendor_name,
                "amount": bill.amount,
                "frequency": bill.frequency.value,
                "category": bill.category.value,
                "is_auto_pay": bill.is_auto_pay,
                "is_active": bill.is_active,
                "alert_days_before": bill.alert_days_before,
                "due_day_of_month": bill.due_day_of_month,
                "due_month": bill.due_month,
                "custom_months": bill.custom_months,
                "next_due_date": bill.next_due_date,
                "display_due_date": (
                    current.due_date if (
                        current is not None
                        and current.status == OccurrenceStatus.OVERDUE
                    ) else bill.next_due_date
                ),
                "last_paid_at": last_paid_at,
                "current_occurrence_id": current_occ_id,
                "current_period_status": current_status,
                "days_overdue": days_overdue,
                "days_until_due": days_until_due,
                "late_tier": late_tier,
            })

        # Sort: red → orange → yellow → none, then by next_due_date asc
        tier_order = {"red": 0, "orange": 1, "yellow": 2, "none": 3}
        items.sort(key=lambda r: (
            tier_order.get(r["late_tier"], 3),
            r["next_due_date"] or datetime.max.replace(tzinfo=timezone.utc),
        ))
        return items

    async def mark_bill_current_paid(self, bill_id: int) -> Optional[BillOccurrence]:
        """Mark the current-period occurrence of a bill as paid.

        Resolves the same "current" occurrence used by the Master List
        (earliest unpaid). If none exists, generates occurrences first
        and tries again. Returns the paid `BillOccurrence` or None.
        """
        bill = await self.get_bill(bill_id)
        if not bill:
            return None

        async def _find_current() -> Optional[BillOccurrence]:
            r = await self.db.execute(
                select(BillOccurrence)
                .where(
                    BillOccurrence.recurring_bill_id == bill_id,
                    BillOccurrence.status.in_([
                        OccurrenceStatus.OVERDUE,
                        OccurrenceStatus.DUE_SOON,
                        OccurrenceStatus.UPCOMING,
                    ]),
                )
                .order_by(BillOccurrence.due_date.asc())
                .limit(1)
            )
            return r.scalar_one_or_none()

        occ = await _find_current()
        if occ is None:
            await self.generate_occurrences()
            occ = await _find_current()
        if occ is None:
            return None

        return await self.mark_paid(occ.id)

    async def get_cash_flow_summary(self) -> dict:
        """Get aggregated cash flow summary."""
        now = datetime.now(timezone.utc)
        seven_days = now + timedelta(days=7)
        thirty_days = now + timedelta(days=30)

        # Upcoming 7 days (only bills toggled into cashflow)
        result_7d = await self.db.execute(
            select(func.coalesce(func.sum(BillOccurrence.amount), 0.0))
            .join(RecurringBill)
            .where(
                RecurringBill.is_active == True,  # noqa: E712
                RecurringBill.user_id == self.user_id,
                BillOccurrence.included_in_cashflow == True,  # noqa: E712
                BillOccurrence.due_date >= now,
                BillOccurrence.due_date <= seven_days,
                BillOccurrence.status.notin_([OccurrenceStatus.SKIPPED, OccurrenceStatus.PAID]),
            )
        )
        total_7d = float(result_7d.scalar() or 0.0)

        # Upcoming 30 days (only bills toggled into cashflow)
        result_30d = await self.db.execute(
            select(func.coalesce(func.sum(BillOccurrence.amount), 0.0))
            .join(RecurringBill)
            .where(
                RecurringBill.is_active == True,  # noqa: E712
                RecurringBill.user_id == self.user_id,
                BillOccurrence.included_in_cashflow == True,  # noqa: E712
                BillOccurrence.due_date >= now,
                BillOccurrence.due_date <= thirty_days,
                BillOccurrence.status.notin_([OccurrenceStatus.SKIPPED, OccurrenceStatus.PAID]),
            )
        )
        total_30d = float(result_30d.scalar() or 0.0)

        # Overdue total (only bills toggled into cashflow)
        result_overdue = await self.db.execute(
            select(func.coalesce(func.sum(BillOccurrence.amount), 0.0))
            .join(RecurringBill)
            .where(
                RecurringBill.is_active == True,  # noqa: E712
                RecurringBill.user_id == self.user_id,
                BillOccurrence.included_in_cashflow == True,  # noqa: E712
                BillOccurrence.status == OccurrenceStatus.OVERDUE,
            )
        )
        total_overdue = float(result_overdue.scalar() or 0.0)

        # Bank balance from AppSetting
        balance_result = await self.db.execute(
            select(AppSetting).where(AppSetting.key == "bank_balance", AppSetting.user_id == self.user_id)
        )
        balance_setting = balance_result.scalar_one_or_none()
        bank_balance = float(balance_setting.value) if balance_setting else 0.0

        # Outstanding checks — calculated from PaymentOut records
        from app.services.payments_out_service import PaymentsOutService
        po_svc = PaymentsOutService(self.db, self.user_id)
        outstanding_checks = await po_svc.get_total_outstanding()

        # Expected receivables from ReceivableCheck table (sum of collect=True)
        recv_result = await self.db.execute(
            select(func.coalesce(func.sum(ReceivableCheck.invoiced_amount), 0.0))
            .where(
                ReceivableCheck.collect == True,  # noqa: E712
                ReceivableCheck.user_id == self.user_id,
            )
        )
        expected_receivables = float(recv_result.scalar() or 0.0)

        # Outstanding payables (invoices to pay) — only those toggled into cashflow
        payables_result = await self.db.execute(
            select(func.coalesce(func.sum(Payable.amount), 0.0)).where(
                Payable.user_id == self.user_id,
                Payable.status.in_([PayableStatus.OUTSTANDING, PayableStatus.OVERDUE]),
                Payable.is_junked == False,  # noqa: E712
                Payable.is_permanent == False,  # noqa: E712
                Payable.included_in_cashflow == True,  # noqa: E712
            )
        )
        total_payables = float(payables_result.scalar() or 0.0)

        real_available = bank_balance + expected_receivables - outstanding_checks - total_30d - total_overdue

        # Populate bills due soon (within 7 days, not paid/skipped)
        due_soon_result = await self.db.execute(
            select(BillOccurrence)
            .join(RecurringBill)
            .options(joinedload(BillOccurrence.recurring_bill))
            .where(
                RecurringBill.is_active == True,  # noqa: E712
                RecurringBill.user_id == self.user_id,
                BillOccurrence.due_date >= now,
                BillOccurrence.due_date <= seven_days,
                BillOccurrence.status.notin_([OccurrenceStatus.SKIPPED, OccurrenceStatus.PAID]),
            )
            .order_by(BillOccurrence.due_date.asc())
        )
        due_soon_occs = due_soon_result.unique().scalars().all()
        bills_due_soon = []
        for occ in due_soon_occs:
            bill = occ.recurring_bill
            bills_due_soon.append({
                "id": occ.id,
                "recurring_bill_id": occ.recurring_bill_id,
                "due_date": occ.due_date,
                "amount": occ.amount,
                "status": occ.status.value,
                "notes": occ.notes,
                "bill_name": bill.name if bill else None,
                "vendor_name": bill.vendor_name if bill else None,
                "category": bill.category.value if bill else None,
                "is_auto_pay": bill.is_auto_pay if bill else None,
                "paid_at": occ.paid_at,
                "matched_invoice_id": occ.matched_invoice_id,
                "days_overdue": None,
                "included_in_cashflow": occ.included_in_cashflow,
                "created_at": occ.created_at,
            })

        # Populate overdue bills (all overdue, regardless of cashflow toggle)
        now_date = datetime.now(timezone.utc).date()
        overdue_result = await self.db.execute(
            select(BillOccurrence)
            .join(RecurringBill)
            .options(joinedload(BillOccurrence.recurring_bill))
            .where(
                RecurringBill.is_active == True,  # noqa: E712
                RecurringBill.user_id == self.user_id,
                BillOccurrence.status == OccurrenceStatus.OVERDUE,
            )
            .order_by(BillOccurrence.due_date.asc())
        )
        overdue_occs = overdue_result.unique().scalars().all()
        overdue_bills = []
        for occ in overdue_occs:
            bill = occ.recurring_bill
            days_overdue = (now_date - occ.due_date.date()).days
            overdue_bills.append({
                "id": occ.id,
                "recurring_bill_id": occ.recurring_bill_id,
                "due_date": occ.due_date,
                "amount": occ.amount,
                "status": occ.status.value,
                "notes": occ.notes,
                "bill_name": bill.name if bill else None,
                "vendor_name": bill.vendor_name if bill else None,
                "category": bill.category.value if bill else None,
                "is_auto_pay": bill.is_auto_pay if bill else None,
                "paid_at": occ.paid_at,
                "matched_invoice_id": occ.matched_invoice_id,
                "days_overdue": days_overdue,
                "included_in_cashflow": occ.included_in_cashflow,
                "created_at": occ.created_at,
            })

        return {
            "bank_balance": bank_balance,
            "outstanding_checks": outstanding_checks,
            "expected_receivables": expected_receivables,
            "total_payables": total_payables,
            "total_upcoming_7d": total_7d,
            "total_upcoming_30d": total_30d,
            "total_overdue": total_overdue,
            "real_available": real_available,
            "bills_due_soon": bills_due_soon,
            "overdue_bills": overdue_bills,
        }

    async def get_calendar_view(
        self, start_date: datetime, end_date: datetime
    ) -> dict[str, list[dict]]:
        """Return occurrences grouped by date string for calendar display."""
        occurrences = await self.list_occurrences(
            start_date=start_date, end_date=end_date
        )
        grouped: dict[str, list[dict]] = {}
        for occ in occurrences:
            key = occ["due_date"].strftime("%Y-%m-%d")
            grouped.setdefault(key, []).append(occ)
        return grouped

    async def delete_all_bills(self) -> int:
        """Hard-delete ALL recurring bills and their occurrences for this user."""
        # Get bill IDs for this user
        result = await self.db.execute(
            select(RecurringBill.id).where(RecurringBill.user_id == self.user_id)
        )
        bill_ids = [row[0] for row in result.all()]
        if not bill_ids:
            return 0
        # Delete notifications referencing these bills
        await self.db.execute(delete(Notification).where(Notification.related_bill_id.in_(bill_ids)))
        # Delete all occurrences for these bills
        await self.db.execute(delete(BillOccurrence).where(BillOccurrence.recurring_bill_id.in_(bill_ids)))
        # Delete the recurring bills
        await self.db.execute(delete(RecurringBill).where(RecurringBill.id.in_(bill_ids)))
        await self.db.flush()
        return len(bill_ids)

    async def bulk_import(self, bills_data: list[dict]) -> list[RecurringBill]:
        """Import multiple recurring bills from a list of dicts, skipping duplicates."""
        # Pre-load existing bill name+vendor pairs for dedup
        existing_result = await self.db.execute(
            select(RecurringBill.name, RecurringBill.vendor_name).where(
                RecurringBill.is_active == True,
                RecurringBill.user_id == self.user_id,
            )
        )
        existing_keys = {
            (row.name.strip().lower(), row.vendor_name.strip().lower())
            for row in existing_result.all()
        }

        created = []
        for data in bills_data:
            key = (data["name"].strip().lower(), data["vendor_name"].strip().lower())
            if key in existing_keys:
                continue
            bill = await self.create_bill(data)
            created.append(bill)
            existing_keys.add(key)
        await self.db.flush()
        return created
