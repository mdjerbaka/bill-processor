import asyncio
from app.core.database import engine
from sqlalchemy import text

async def check():
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT id, key, user_id FROM app_settings WHERE key = 'imap_host' ORDER BY id"))
        rows = r.fetchall()
        print(f"Found {len(rows)} imap_host rows:")
        for row in rows:
            print(f"  id={row[0]}, key={row[1]}, user_id={row[2]}")
        if len(rows) > 1:
            ids_to_delete = [row[0] for row in rows[1:]]
            for did in ids_to_delete:
                await conn.execute(text(f"DELETE FROM app_settings WHERE id = {did}"))
                print(f"  Deleted duplicate row id={did}")
            print("Duplicates cleaned up!")
        else:
            print("No duplicates to clean.")

asyncio.run(check())
