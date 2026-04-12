"""Check santimaw account real balance data."""
import asyncio
from sqlalchemy import text
from app.core.database import engine

async def check():
    async with engine.connect() as conn:
        # List all tables
        r = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
        ))
        tables = r.fetchall()
        print("=== Tables ===")
        for t in tables:
            print(f"  {t[0]}")

        # Find user table
        user_tables = [t[0] for t in tables if 'user' in t[0].lower()]
        print(f"\nUser tables: {user_tables}")

        if user_tables:
            for tbl in user_tables:
                r = await conn.execute(text(f"SELECT * FROM {tbl} LIMIT 5"))
                cols = r.keys()
                rows = r.fetchall()
                print(f"\n=== {tbl} (cols: {list(cols)}) ===")
                for row in rows:
                    print(f"  {dict(zip(cols, row))}")

    await engine.dispose()

asyncio.run(check())
