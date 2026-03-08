import asyncio
from app.core.database import async_session_factory
from app.models.models import Attachment, Invoice
from sqlalchemy import select

async def check():
    async with async_session_factory() as db:
        r = await db.execute(select(Attachment))
        atts = r.scalars().all()
        for a in atts:
            print(f'ATT {a.id}: email={a.email_id} file={a.filename} path={a.file_path}')
        r2 = await db.execute(select(Invoice))
        invs = r2.scalars().all()
        for i in invs:
            print(f'INV {i.id}: att={i.attachment_id} email={i.email_id} status={i.status}')

asyncio.run(check())
