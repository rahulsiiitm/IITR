import asyncio
import logging
from backend.database import engine, Base
from backend.models import Session, Message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_db():
    logger.info("Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully!")

if __name__ == "__main__":
    asyncio.run(init_db())
