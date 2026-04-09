"""
Add included_in_cashflow column to recurring_bills and exclude Payroll/401k bills.
Run: python add_bill_cashflow_flag.py
"""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

async def main():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        # 1. Add column if not exists
        result = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'recurring_bills' AND column_name = 'included_in_cashflow'
        """))
        if not result.fetchone():
            await conn.execute(text("""
                ALTER TABLE recurring_bills
                ADD COLUMN included_in_cashflow BOOLEAN DEFAULT true NOT NULL
            """))
            print("Added included_in_cashflow column to recurring_bills")
        else:
            print("Column already exists")

        # 2. Set Payroll and 401k bills to excluded
        result = await conn.execute(text("""
            UPDATE recurring_bills
            SET included_in_cashflow = false
            WHERE LOWER(name) LIKE '%payroll%' OR LOWER(name) LIKE '%401k%' OR LOWER(name) LIKE '%401(k)%'
            RETURNING id, name
        """))
        excluded = result.fetchall()
        for row in excluded:
            print(f"  Excluded from cash flow: [{row[0]}] {row[1]}")

        # 3. Also update existing UPCOMING/DUE_SOON occurrences for those bills
        if excluded:
            bill_ids = [row[0] for row in excluded]
            result = await conn.execute(text("""
                UPDATE bill_occurrences
                SET included_in_cashflow = false
                WHERE recurring_bill_id = ANY(:bill_ids)
                AND status IN ('UPCOMING', 'DUE_SOON')
            """), {"bill_ids": bill_ids})
            print(f"  Updated {result.rowcount} occurrences to excluded")

        # 4. Stamp alembic
        await conn.execute(text("""
            UPDATE alembic_version SET version_num = 'h8c9d0e1f2g3'
        """))
        print("Stamped alembic version to h8c9d0e1f2g3")

    await engine.dispose()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
