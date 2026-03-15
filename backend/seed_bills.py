"""Seed 10 test recurring bills with varied due dates and categories."""
import asyncio
from datetime import date, timedelta
from app.core.database import engine, async_session_factory
from app.models.models import RecurringBill, BillFrequency, BillCategory

BILLS = [
    dict(name="Office Rent", vendor_name="Cascade Property Mgmt", amount=4200.00,
         frequency=BillFrequency.MONTHLY, due_day_of_month=1,
         category=BillCategory.MORTGAGE, is_auto_pay=True, alert_days_before=5,
         notes="Main office lease - 123 Industrial Way"),
    dict(name="Truck Insurance", vendor_name="State Farm Commercial", amount=1850.00,
         frequency=BillFrequency.MONTHLY, due_day_of_month=5,
         category=BillCategory.VEHICLE_INSURANCE, is_auto_pay=True, alert_days_before=7,
         notes="Fleet policy - 6 trucks"),
    dict(name="Internet & Phone", vendor_name="Comcast Business", amount=289.99,
         frequency=BillFrequency.MONTHLY, due_day_of_month=10,
         category=BillCategory.INTERNET, is_auto_pay=True, alert_days_before=3,
         notes="Office internet + 4 phone lines"),
    dict(name="Equipment Lease - Excavator", vendor_name="United Rentals", amount=3500.00,
         frequency=BillFrequency.MONTHLY, due_day_of_month=15,
         category=BillCategory.LOAN, is_auto_pay=False, alert_days_before=7,
         notes="CAT 320 excavator - 36mo lease"),
    dict(name="Workers Comp Premium", vendor_name="Liberty Mutual", amount=2100.00,
         frequency=BillFrequency.QUARTERLY, due_day_of_month=20, due_month=1,
         category=BillCategory.WORKERS_COMP, is_auto_pay=False, alert_days_before=14,
         notes="Quarterly premium - policy #WC-445892"),
    dict(name="Waste Disposal", vendor_name="Waste Management", amount=475.00,
         frequency=BillFrequency.MONTHLY, due_day_of_month=18,
         category=BillCategory.TRASH, is_auto_pay=False, alert_days_before=5,
         notes="Dumpster service - 2 sites"),
    dict(name="Accounting Software", vendor_name="Intuit QuickBooks", amount=85.00,
         frequency=BillFrequency.MONTHLY, due_day_of_month=22,
         category=BillCategory.SUBSCRIPTION, is_auto_pay=True, alert_days_before=3,
         notes="QBO Plus subscription"),
    dict(name="General Liability Insurance", vendor_name="Hartford", amount=4800.00,
         frequency=BillFrequency.SEMI_ANNUAL, due_day_of_month=1, due_month=4,
         category=BillCategory.LIABILITY_INSURANCE, is_auto_pay=False, alert_days_before=14,
         notes="$2M GL policy - semi-annual premium"),
    dict(name="Cell Phone Plan", vendor_name="Verizon Business", amount=520.00,
         frequency=BillFrequency.MONTHLY, due_day_of_month=25,
         category=BillCategory.PHONE, is_auto_pay=True, alert_days_before=3,
         notes="8 lines - crew phones"),
    dict(name="Contractor License Renewal", vendor_name="WA Dept of L&I", amount=350.00,
         frequency=BillFrequency.ANNUAL, due_day_of_month=15, due_month=6,
         category=BillCategory.LICENSE, is_auto_pay=False, alert_days_before=30,
         notes="General contractor license renewal"),
]


async def main():
    async with async_session_factory() as db:
        for b in BILLS:
            # Compute next_due_date based on frequency
            today = date.today()
            day = b["due_day_of_month"]
            freq = b["frequency"]

            if freq == BillFrequency.MONTHLY:
                # Next occurrence this month or next
                try:
                    candidate = today.replace(day=day)
                except ValueError:
                    import calendar
                    last = calendar.monthrange(today.year, today.month)[1]
                    candidate = today.replace(day=min(day, last))
                if candidate < today:
                    m = today.month + 1
                    y = today.year + (1 if m > 12 else 0)
                    m = m if m <= 12 else m - 12
                    import calendar
                    last = calendar.monthrange(y, m)[1]
                    candidate = date(y, m, min(day, last))
                next_due = candidate
            else:
                # For quarterly/semi-annual/annual, use due_month
                dm = b.get("due_month", 1)
                try:
                    candidate = date(today.year, dm, day)
                except ValueError:
                    import calendar
                    last = calendar.monthrange(today.year, dm)[1]
                    candidate = date(today.year, dm, min(day, last))
                if candidate < today:
                    if freq == BillFrequency.QUARTERLY:
                        candidate = date(today.year, dm + 3, day) if dm + 3 <= 12 else date(today.year + 1, (dm + 3 - 12), day)
                    elif freq == BillFrequency.SEMI_ANNUAL:
                        candidate = date(today.year, dm + 6, day) if dm + 6 <= 12 else date(today.year + 1, (dm + 6 - 12), day)
                    else:
                        candidate = date(today.year + 1, dm, day)
                next_due = candidate

            bill = RecurringBill(
                name=b["name"],
                vendor_name=b["vendor_name"],
                amount=b["amount"],
                frequency=b["frequency"],
                due_day_of_month=b["due_day_of_month"],
                due_month=b.get("due_month"),
                category=b["category"],
                is_auto_pay=b["is_auto_pay"],
                alert_days_before=b["alert_days_before"],
                notes=b.get("notes"),
                next_due_date=next_due,
                is_active=True,
            )
            db.add(bill)
            print(f"  + {b['name']:40s} ${b['amount']:>10,.2f}  due {next_due}  ({b['frequency'].value})")

        await db.commit()
    print(f"\nSeeded {len(BILLS)} recurring bills.")
    await engine.dispose()

asyncio.run(main())
