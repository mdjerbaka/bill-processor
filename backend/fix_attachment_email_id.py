"""
Make attachments.email_id nullable for manual invoice uploads.
Run: python fix_attachment_email_id.py
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
        await conn.execute(text("""
            ALTER TABLE attachments ALTER COLUMN email_id DROP NOT NULL
        """))
        print("Made attachments.email_id nullable")
    await engine.dispose()
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
