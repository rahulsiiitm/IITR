import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from backend.models import Session, Message

engine = create_async_engine('postgresql+asyncpg://sutra_user:sutra_secure_pass_2026@localhost:5432/sutra_db')
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def test():
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Session))
        sessions = res.scalars().all()
        print('Sessions:', len(sessions))
        for s in sessions:
            print("Session:", s.id)
        
        res = await session.execute(select(Message))
        msgs = res.scalars().all()
        print('Messages:', len(msgs))

asyncio.run(test())
