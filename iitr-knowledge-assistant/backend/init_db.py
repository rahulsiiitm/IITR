import asyncio
import logging
import sys
from backend.database import engine, Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_db():
    max_retries = 5
    for attempt in range(max_retries):
        try:
            logger.info(f"Initializing database tables (Attempt {attempt+1}/{max_retries})...")
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully!")
            return
        except Exception as e:
            logger.warning(f"Database connection failed: {e}")
            if attempt < max_retries - 1:
                logger.info("Retrying in 5 seconds...")
                await asyncio.sleep(5)
            else:
                logger.error("Failed to connect to the database after multiple attempts.")
                sys.exit(1)

if __name__ == "__main__":
    asyncio.run(init_db())
