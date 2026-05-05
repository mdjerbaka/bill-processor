"""Pure-function tests for the recurring bills date generator.

Regression coverage for the bug where a monthly bill whose due-day had
already passed in the current month would never get an occurrence row
generated, making it vanish from the current-month view.
"""

from datetime import date, timedelta

from app.models.models import BillFrequency
from app.services.recurring_bills_service import _generate_dates_in_range


def test_monthly_includes_already_passed_day_this_month():
    # Today is the 20th, bill is due on the 5th. The 5th has already passed
    # this month, but the row must still be generated so it can be flagged
    # OVERDUE and shown in the current-month view.
    today = date(2026, 5, 20)
    end = today + timedelta(days=60)

    dates = _generate_dates_in_range(
        BillFrequency.MONTHLY,
        due_day=5,
        due_month=None,
        start=today,
        end=end,
    )

    assert date(2026, 5, 5) in dates, (
        "MONTHLY occurrence for already-passed day in the current month "
        "must still be generated"
    )
    # And next month's row should also be there
    assert date(2026, 6, 5) in dates


def test_monthly_future_day_this_month_included():
    today = date(2026, 5, 3)
    end = today + timedelta(days=60)
    dates = _generate_dates_in_range(
        BillFrequency.MONTHLY, due_day=15, due_month=None, start=today, end=end
    )
    assert date(2026, 5, 15) in dates
    assert date(2026, 6, 15) in dates


def test_monthly_no_duplicate_dates():
    today = date(2026, 5, 20)
    end = today + timedelta(days=60)
    dates = _generate_dates_in_range(
        BillFrequency.MONTHLY, due_day=5, due_month=None, start=today, end=end
    )
    assert len(dates) == len(set(dates))


def test_quarterly_includes_passed_quarter_this_period():
    # Quarterly starting Jan -> due months Jan, Apr, Jul, Oct
    today = date(2026, 5, 20)  # Apr already passed
    end = today + timedelta(days=120)
    dates = _generate_dates_in_range(
        BillFrequency.QUARTERLY,
        due_day=10,
        due_month=1,
        start=today,
        end=end,
    )
    # April 10 is before today but still in the current quarter window
    assert date(2026, 4, 10) in dates
    assert date(2026, 7, 10) in dates


def test_annual_passed_month_in_current_year_included():
    today = date(2026, 5, 20)
    end = date(2026, 12, 31)
    dates = _generate_dates_in_range(
        BillFrequency.ANNUAL,
        due_day=15,
        due_month=3,  # March 15 — already passed this year
        start=today,
        end=end,
    )
    assert date(2026, 3, 15) in dates


def test_weekly_unchanged_behavior():
    today = date(2026, 5, 1)
    end = today + timedelta(days=21)
    dates = _generate_dates_in_range(
        BillFrequency.WEEKLY, due_day=None, due_month=None, start=today, end=end
    )
    assert dates == [
        date(2026, 5, 1),
        date(2026, 5, 8),
        date(2026, 5, 15),
        date(2026, 5, 22),
    ]
