import asyncio
from pathlib import Path
from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.models import Document
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        raw_dir = settings.data_dir
        if raw_dir.exists():
            for pdf_path in raw_dir.glob("*.pdf"):
                result = await db.execute(select(Document).where(Document.filename == pdf_path.name))
                if not result.scalars().first():
                    title = pdf_path.name.replace(".pdf", "").replace("_", " ").title()
                    doc = Document(filename=pdf_path.name, title=title, status="active")
                    db.add(doc)
            await db.commit()
            print("Populated existing docs!")

if __name__ == "__main__":
    asyncio.run(main())
