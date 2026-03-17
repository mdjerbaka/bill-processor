"""Recurring bills management and cash flow calculations."""

from __future__ import annotations

import calendar
import logging
from datetime import datetime, timedelta, timezone, date
from typing import Optional

from sqlalchemy import select, func, and_, or_, delete
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
    RecurringBill,
)

logger = logging.getLogger(__name__)


def _compute_next_due_date(
    frequency: BillFrequency,
    due_day: Optional[int],
    due_month: Optional[int] = None,
    after: Optional[datetime] = None,
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

    # Default fallback
    return datetime(today.year, today.month, due_day, tzinfo=timezone.utc)


def _generate_dates_in_range(
    frequency: BillFrequency,
    due_day: Optional[int],
    due_month: Optional[int],
    start: date,
    end: date,
) -> list[date]:
    """Generate all occurrence dates within [start, end] for the given frequency."""
    dates = []

    def _safe_date(year: int, month: int, day: int) -> date:
        max_day = calendar.monthrange(year, month)[1]
        return date(year, month, min(day, max_day))

    if frequency == BillFrequency.WEEKLY:
        # Generate one occurrence per week starting from start
        current = start
        while current <= end:
            dates.append(current)
            current += timedelta(days=7)
        return dates

    if frequency == BillFrequency.MONTHLY:
        current = date(start.year, start.month, 1)
        while current <= end:
            candidate = _safe_date(current.year, current.month, due_day)
            if start <= candidate <= end:
                dates.append(candidate)
            # advance month
            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)

    elif frequency == BillFrequency.QUARTERLY:
        base_month = due_month or 1
        quarter_months = sorted(set((base_month + i * 3 - 1) % 12 + 1 for i in range(4)))
        for year in range(start.year, end.year + 1):
            for m in quarter_months:
                candidate = _safe_date(year, m, due_day)
                if start <= candidate <= end:
                    dates.append(candidate)

    elif frequency == BillFrequency.SEMI_ANNUAL:
        base_month = due_month or 1
        semi_months = sorted(set((base_month + i * 6 - 1) % 12 + 1 for i in range(2)))
        for year in range(start.year, end.year + 1):
            for m in semi_months:
                candidate = _safe_date(year, m, due_day)
                if start <= candidate <= end:
                    dates.append(candidate)

    elif frequency == BillFrequency.ANNUAL:
        month = due_month or 1
        for year in range(start.year, end.year + 1):
            candidate = _safe_date(year, month, due_day)
            if start <= candidate <= end:
                dates.append(candidate)

    elif frequency == BillFrequency.BIENNIAL:
        month = due_month or 1
        for year in range(start.year, end.year + 2, 2):
            candidate = _safe_date(year, month, due_day)
            if start <= candidate <= end:
                dates.append(candidate)

    return dates


class RecurringBillsService:
    """Manages recurring bills and their occurrences."""

    def __init__(self, db: AsyncSession):
        self.db = db

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
            category=cat,
            notes=data.get("notes"),
            is_auto_pay=data.get("is_auto_pay", False),
            alert_days_before=data.get("alert_days_before", 7),
        )
        bill.next_due_date = _compute_next_due_date(
            freq, bill.due_day_of_month, bill.due_month
        )
        self.db.add(bill)
        await self.db.flush()
        return bill

    async def update_bill(self, bill_id: int, data: dict) -> Optional[RecurringBill]:
        """Update a recurring bill."""
        result = await self.db.execute(
            select(RecurringBill).where(RecurringBill.id == bill_id)
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

        # Recompute next due date
        bill.next_due_date = _compute_next_due_date(
            bill.frequency, bill.due_day_of_month, bill.due_month
        )
        await self.db.flush()
        return bill

    async def delete_bill(self, bill_id: int) -> bool:
        """Soft-delete a recurring bill (set is_active=False)."""
        result = await self.db.execute(
            select(RecurringBill).where(RecurringBill.id == bill_id)
        )
        bill = result.scalar_one_or_none()
        if not bill:
            return False
        bill.is_active = False
        await self.db.flush()
        return True

    async def get_bill(self, bill_id: int) -> Optional[RecurringBill]:
        """Get a single recurring bill by ID."""
        result = await self.db.execute(
            select(RecurringBill).where(RecurringBill.id == bill_id)
        )
        return result.scalar_one_or_none()

    async def list_bills(self, include_inactive: bool = False) -> list[RecurringBill]:
        """List all recurring bills."""
        q = select(RecurringBill).order_by(RecurringBill.next_due_date.asc())
        if not include_inactive:
            q = q.where(RecurringBill.is_active == True)  # noqa: E712
        result = await self.db.execute(q)
        return list(result.scalars().all())

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
                bill.frequency, bill.due_day_of_month, bill.due_month, today, end_date
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
                )
                self.db.add(occ)
                created_count += 1

            # Update next_due_date on the bill
            bill.next_due_date = _compute_next_due_date(
                bill.frequency, bill.due_day_of_month, bill.due_month
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

    async def skip_occurrence(self, occurrence_id: int) -> Optional[BillOccurrence]:
        """Skip a bill occurrence."""
        result = await self.db.execute(
            select(BillOccurrence).where(BillOccurrence.id == occurrence_id)
        )
        occ = result.scalar_one_or_none()
        if occ:
            occ.status = OccurrenceStatus.SKIPPED
            await self.db.flush()
        return occ

    async def mark_paid(self, occurrence_id: int) -> Optional[BillOccurrence]:
        """Mark a bill occurrence as paid (local tracking only, not synced to QB)."""
        result = await self.db.execute(
            select(BillOccurrence).where(BillOccurrence.id == occurrence_id)
        )
        occ = result.scalar_one_or_none()
        if occ:
            occ.status = OccurrenceStatus.PAID
            occ.paid_at = datetime.now(timezone.utc)
            await self.db.flush()
        return occ

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
            .where(RecurringBill.is_active == True)  # noqa: E712
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
                "created_at": occ.created_at,
            })
        return enriched

    async def get_cash_flow_summary(self) -> dict:
        """Get aggregated cash flow summary."""
        now = datetime.now(timezone.utc)
        seven_days = now + timedelta(days=7)
        thirty_days = now + timedelta(days=30)

        # Upcoming 7 days
        result_7d = await self.db.execute(
            select(func.coalesce(func.sum(BillOccurrence.amount), 0.0))
            .join(RecurringBill)
            .where(
                RecurringBill.is_active == True,  # noqa: E712
                BillOccurrence.due_date >= now,
                BillOccurrence.due_date <= seven_days,
                BillOccurrence.status.notin_([OccurrenceStatus.SKIPPED, OccurrenceStatus.PAID]),
            )
        )
        total_7d = float(result_7d.scalar() or 0.0)

        # Upcoming 30 days
        result_30d = await self.db.execute(
            select(func.coalesce(func.sum(BillOccurrence.amount), 0.0))
            .join(RecurringBill)
            .where(
                RecurringBill.is_active == True,  # noqa: E712
                BillOccurrence.due_date >= now,
                BillOccurrence.due_date <= thirty_days,
                BillOccurrence.status.notin_([OccurrenceStatus.SKIPPED, OccurrenceStatus.PAID]),
            )
        )
        total_30d = float(result_30d.scalar() or 0.0)

        # Overdue total
        result_overdue = await self.db.execute(
            select(func.coalesce(func.sum(BillOccurrence.amount), 0.0))
            .join(RecurringBill)
            .where(
                RecurringBill.is_active == True,  # noqa: E712
                BillOccurrence.status == OccurrenceStatus.OVERDUE,
            )
        )
        total_overdue = float(result_overdue.scalar() or 0.0)

        # Bank balance from AppSetting
        balance_result = await self.db.execute(
            select(AppSetting).where(AppSetting.key == "bank_balance")
        )
        balance_setting = balance_result.scalar_one_or_none()
        bank_balance = float(balance_setting.value) if balance_setting else 0.0

        # Outstanding checks from AppSetting
        checks_result = await self.db.execute(
            select(AppSetting).where(AppSetting.key == "outstanding_checks")
        )
        checks_setting = checks_result.scalar_one_or_none()
        outstanding_checks = float(checks_setting.value) if checks_setting else 0.0

        real_available = bank_balance - outstanding_checks - total_30d - total_overdue

        return {
            "bank_balance": bank_balance,
            "outstanding_checks": outstanding_checks,
            "total_upcoming_7d": total_7d,
            "total_upcoming_30d": total_30d,
            "total_overdue": total_overdue,
            "real_available": real_available,
            "bills_due_soon": [],
            "overdue_bills": [],
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
        """Hard-delete ALL recurring bills and their occurrences."""
        # Delete notifications referencing bills
        await self.db.execute(delete(Notification).where(Notification.related_bill_id.isnot(None)))
        # Delete all occurrences (FK constraint)
        await self.db.execute(delete(BillOccurrence))
        # Delete all recurring bills
        result = await self.db.execute(delete(RecurringBill))
        await self.db.flush()
        return result.rowcount

    async def bulk_import(self, bills_data: list[dict]) -> list[RecurringBill]:
        """Import multiple recurring bills from a list of dicts, skipping duplicates."""
        # Pre-load existing bill name+vendor pairs for dedup
        existing_result = await self.db.execute(
            select(RecurringBill.name, RecurringBill.vendor_name).where(
                RecurringBill.is_active == True
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
