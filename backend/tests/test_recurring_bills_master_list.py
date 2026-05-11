"""Tests for the recurring bills Master List derived view + toggle.

Covers:
- `display_due_date` shows the past overdue date (not the misleading
  future `next_due_date`) when a bill is overdue.
- `toggle_active` flips `is_active` and hides paused bills from the
  default Master List, but includes them when `include_inactive=True`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.models import (
    BillFrequency,
    BillCategory,
    BillOccurrence,
    OccurrenceStatus,
    RecurringBill,
)
from app.services.recurring_bills_service import RecurringBillsService


@pytest.mark.asyncio
async def test_master_list_overdue_uses_past_due_date_not_future(db_session, test_user):
    """An overdue bill must show the past due date in display_due_date.

    Without this fix, the Master List displayed `bill.next_due_date`
    (always a future date) while still flagging the bill as Late, which
    confused the client ("future date but flagged late").
    """
    svc = RecurringBillsService(db_session, test_user.id)

    now = datetime.now(timezone.utc)
    past_due = now - timedelta(days=10)
    future_due = now + timedelta(days=20)

    bill = RecurringBill(
        user_id=test_user.id,
        name="Test Monthly Bill",
        vendor_name="Acme",
        amount=100.0,
        frequency=BillFrequency.MONTHLY,
        due_day_of_month=1,
        category=BillCategory.OTHER,
        is_active=True,
        next_due_date=future_due,
    )
    db_session.add(bill)
    await db_session.flush()

    # Overdue occurrence in the past — should drive display_due_date
    occ = BillOccurrence(
        recurring_bill_id=bill.id,
        due_date=past_due,
        amount=100.0,
        status=OccurrenceStatus.OVERDUE,
    )
    db_session.add(occ)
    await db_session.flush()

    items = await svc.get_master_list()
    assert len(items) == 1
    row = items[0]

    assert row["late_tier"] in ("yellow", "orange", "red"), (
        "an overdue occurrence must produce a non-'none' late_tier"
    )
    assert row["display_due_date"] == past_due, (
        "display_due_date must be the past overdue date, not the future "
        f"next_due_date. Got display={row['display_due_date']!r}, "
        f"past={past_due!r}"
    )
    assert row["next_due_date"] == future_due, (
        "next_due_date is preserved unchanged for sorting / back-compat"
    )


@pytest.mark.asyncio
async def test_master_list_upcoming_uses_next_due_date(db_session, test_user):
    """When not overdue, display_due_date == next_due_date (no behavior change)."""
    svc = RecurringBillsService(db_session, test_user.id)

    now = datetime.now(timezone.utc)
    future_due = now + timedelta(days=15)

    bill = RecurringBill(
        user_id=test_user.id,
        name="Upcoming Bill",
        vendor_name="Acme",
        amount=50.0,
        frequency=BillFrequency.MONTHLY,
        due_day_of_month=15,
        category=BillCategory.OTHER,
        is_active=True,
        next_due_date=future_due,
    )
    db_session.add(bill)
    await db_session.flush()

    occ = BillOccurrence(
        recurring_bill_id=bill.id,
        due_date=future_due,
        amount=50.0,
        status=OccurrenceStatus.UPCOMING,
    )
    db_session.add(occ)
    await db_session.flush()

    items = await svc.get_master_list()
    assert len(items) == 1
    row = items[0]
    assert row["late_tier"] == "none"
    assert row["display_due_date"] == future_due
    assert row["next_due_date"] == future_due


@pytest.mark.asyncio
async def test_toggle_active_hides_bill_from_default_master_list(db_session, test_user):
    """Paused bills are excluded from the Master List by default,
    included when include_inactive=True."""
    svc = RecurringBillsService(db_session, test_user.id)

    now = datetime.now(timezone.utc)
    bill = RecurringBill(
        user_id=test_user.id,
        name="Toggleable Bill",
        vendor_name="Vendor",
        amount=200.0,
        frequency=BillFrequency.MONTHLY,
        due_day_of_month=10,
        category=BillCategory.OTHER,
        is_active=True,
        next_due_date=now + timedelta(days=5),
    )
    db_session.add(bill)
    await db_session.flush()

    # Sanity: visible by default
    items = await svc.get_master_list()
    assert any(r["id"] == bill.id for r in items)

    # Pause it
    toggled = await svc.toggle_active(bill.id)
    assert toggled is not None
    assert toggled.is_active is False

    # Hidden by default
    default_items = await svc.get_master_list()
    assert all(r["id"] != bill.id for r in default_items), (
        "paused bills must be hidden from the default Master List"
    )

    # Visible when include_inactive=True, with is_active=False on the row
    all_items = await svc.get_master_list(include_inactive=True)
    matching = [r for r in all_items if r["id"] == bill.id]
    assert len(matching) == 1
    assert matching[0]["is_active"] is False

    # Resume it
    resumed = await svc.toggle_active(bill.id)
    assert resumed is not None
    assert resumed.is_active is True

    items_after = await svc.get_master_list()
    assert any(r["id"] == bill.id and r["is_active"] is True for r in items_after)


@pytest.mark.asyncio
async def test_toggle_active_returns_none_for_unknown_bill(db_session, test_user):
    svc = RecurringBillsService(db_session, test_user.id)
    assert await svc.toggle_active(999_999) is None
