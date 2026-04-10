"""Seed Week 3 & 4 recurring bills for Santimaw account."""
import asyncio
from app.core.database import async_session_factory
from app.models.models import User, RecurringBill, BillFrequency, BillCategory
from sqlalchemy import select

WEEK3_BILLS = [
    dict(name="Quarterly taxes due?", vendor_name="Quarterly Taxes", amount=19370.00, due_day_of_month=15, category=BillCategory.TAXES, is_auto_pay=False),
    dict(name="Liability", vendor_name="Liability Insurance", amount=931.83, due_day_of_month=15, category=BillCategory.LIABILITY_INSURANCE, is_auto_pay=True),
    dict(name="Progressive", vendor_name="Progressive", amount=109.92, due_day_of_month=15, category=BillCategory.VEHICLE_INSURANCE, is_auto_pay=True),
    dict(name="Spectrum - Dave", vendor_name="Spectrum", amount=79.99, due_day_of_month=16, category=BillCategory.INTERNET, is_auto_pay=True),
    dict(name="Chewy Life Insurance (Northwestern Mutual)", vendor_name="Northwestern Mutual", amount=98.17, due_day_of_month=17, category=BillCategory.LIFE_INSURANCE, is_auto_pay=True),
    dict(name="Copilot", vendor_name="Copilot", amount=28.45, due_day_of_month=18, category=BillCategory.SUBSCRIPTION, is_auto_pay=True),
    dict(name="Eversource Office Gas (? auto pay)", vendor_name="Eversource", amount=181.62, due_day_of_month=18, category=BillCategory.OTHER, is_auto_pay=True),
    dict(name="Spectrum - Office autopay with Amex", vendor_name="Spectrum", amount=112.13, due_day_of_month=19, category=BillCategory.INTERNET, is_auto_pay=True),
    dict(name="Dan's Cornerstone Equity", vendor_name="Cornerstone Equity", amount=2000.00, due_day_of_month=19, category=BillCategory.LOAN, is_auto_pay=True),
    dict(name="Office West Boylston Light account #65686", vendor_name="Boylston Light", amount=337.54, due_day_of_month=20, category=BillCategory.ELECTRIC, is_auto_pay=True),
    dict(name="Dan West Boylston Light account #50505", vendor_name="Boylston Light", amount=155.03, due_day_of_month=20, category=BillCategory.ELECTRIC, is_auto_pay=True),
]

WEEK4_BILLS = [
    dict(name="Eric's truck", vendor_name="Eric's Truck Payment", amount=913.87, due_day_of_month=22, category=BillCategory.VEHICLE, is_auto_pay=False),
    dict(name="Dave Denali Insurance (Farmers)", vendor_name="Farmers Insurance", amount=146.16, due_day_of_month=22, category=BillCategory.VEHICLE_INSURANCE, is_auto_pay=False),
    dict(name="DCU Steph", vendor_name="DCU", amount=704.60, due_day_of_month=22, category=BillCategory.LOAN, is_auto_pay=False),
    dict(name="Verizon", vendor_name="Verizon", amount=650.00, due_day_of_month=23, category=BillCategory.PHONE, is_auto_pay=False),
    dict(name="Dave's Cornerstone Equity", vendor_name="Cornerstone Equity", amount=801.42, due_day_of_month=25, category=BillCategory.LOAN, is_auto_pay=False),
    dict(name="Boylston Light", vendor_name="Boylston Light", amount=201.36, due_day_of_month=25, category=BillCategory.ELECTRIC, is_auto_pay=False),
    dict(name="Chewy Student Loan (shows up as SoFi in bank account)", vendor_name="SoFi", amount=910.01, due_day_of_month=25, category=BillCategory.LOAN, is_auto_pay=False),
    dict(name="Dan Chase", vendor_name="Chase", amount=4951.27, due_day_of_month=25, category=BillCategory.CREDIT_CARD, is_auto_pay=False),
    dict(name="Flywheel", vendor_name="Flywheel", amount=15.00, due_day_of_month=26, category=BillCategory.SUBSCRIPTION, is_auto_pay=False),
    dict(name="Chewy Peloton", vendor_name="Peloton", amount=95.41, due_day_of_month=28, category=BillCategory.SUBSCRIPTION, is_auto_pay=False),
    dict(name="Northwest Mutual", vendor_name="Northwestern Mutual", amount=188.52, due_day_of_month=28, category=BillCategory.LIFE_INSURANCE, is_auto_pay=False),
    dict(name="Commercial Auto Safety Insurance", vendor_name="Commercial Auto Safety Insurance", amount=687.84, due_day_of_month=28, category=BillCategory.VEHICLE_INSURANCE, is_auto_pay=False),
    dict(name="Dan's truck Safety insurance", vendor_name="Dan's Truck Safety Insurance", amount=239.40, due_day_of_month=29, category=BillCategory.VEHICLE_INSURANCE, is_auto_pay=False, notes="payment link"),
    dict(name="MSB Commercial", vendor_name="MSB Commercial", amount=1898.06, due_day_of_month=29, category=BillCategory.LOAN, is_auto_pay=False),
    dict(name="NG Realty", vendor_name="NG Realty", amount=1650.00, due_day_of_month=30, category=BillCategory.MORTGAGE, is_auto_pay=False),
    dict(name="Open AI", vendor_name="OpenAI", amount=20.00, due_day_of_month=30, category=BillCategory.SUBSCRIPTION, is_auto_pay=False),
    dict(name="Jaqui car payment", vendor_name="Jaqui Car Payment", amount=783.18, due_day_of_month=30, category=BillCategory.VEHICLE, is_auto_pay=False),
]


async def main():
    async with async_session_factory() as db:
        # Find Santimaw user
        result = await db.execute(select(User))
        users = result.scalars().all()
        for u in users:
            print(f"  ID={u.id} username={u.username}")

        # Find the Santimaw account
        santimaw = None
        for u in users:
            uname = (u.username or "").lower()
            if "santimaw" in uname or "julieann" in uname or "lamy" in uname:
                santimaw = u
                break

        if not santimaw:
            # Default to first non-admin user, or user 1
            santimaw = users[0] if users else None
            if not santimaw:
                print("No users found!")
                return
            print(f"\nUsing first user: ID={santimaw.id} username={santimaw.username}")
        else:
            print(f"\nFound Santimaw account: ID={santimaw.id} username={santimaw.username}")

        user_id = santimaw.id

        # Check existing bills to avoid duplicates
        existing = await db.execute(
            select(RecurringBill.name).where(RecurringBill.user_id == user_id)
        )
        existing_names = {r.lower() for r in existing.scalars().all()}
        print(f"\nExisting bills: {len(existing_names)}")

        count = 0
        all_bills = WEEK3_BILLS + WEEK4_BILLS
        for bill_data in all_bills:
            if bill_data["name"].lower() in existing_names:
                print(f"  SKIP (exists): {bill_data['name']}")
                continue
            bill = RecurringBill(
                user_id=user_id,
                frequency=BillFrequency.MONTHLY,
                is_active=True,
                alert_days_before=7,
                included_in_cashflow=True,
                **bill_data,
            )
            db.add(bill)
            count += 1
            print(f"  ADD: {bill_data['name']} - ${bill_data['amount']:,.2f} (due day {bill_data['due_day_of_month']})")

        await db.commit()
        print(f"\nDone! Added {count} recurring bills for user {user_id}.")


asyncio.run(main())
