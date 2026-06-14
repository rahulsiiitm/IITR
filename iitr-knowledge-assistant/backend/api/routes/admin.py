from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from backend.database import get_db
from backend.models import Session, Message, Document
from backend.config import settings
import shutil
import os
from pathlib import Path
from backend.indexing.build_index import index_single_document
import logging
from fastapi import FastAPI

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/sessions")
async def get_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).order_by(Session.created_at.desc()))
    sessions = result.scalars().all()
    return [{"id": s.id, "created_at": s.created_at} for s in sessions]

@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Message).where(Message.session_id == session_id).order_by(Message.created_at))
    messages = result.scalars().all()
    return [{"id": m.id, "role": m.role, "content": m.content, "sources": m.sources, "created_at": m.created_at} for m in messages]

@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    session_count_res = await db.execute(select(func.count(Session.id)))
    session_count = session_count_res.scalar() or 0
    
    message_count_res = await db.execute(select(func.count(Message.id)))
    message_count = message_count_res.scalar() or 0
    
    return {
        "total_sessions": session_count,
        "total_messages": message_count,
        "llm_model": settings.ollama_model,
        "embedding_model": settings.embedding_model,
        "rerank_model": settings.rerank_model,
    }

@router.get("/settings")
async def get_settings():
    s_dict = settings.model_dump()
    if s_dict.get("api_key"):
        s_dict["api_key"] = "***HIDDEN***"
    if s_dict.get("database_url"):
        s_dict["database_url"] = "***HIDDEN***"
    s_dict["data_dir"] = str(s_dict["data_dir"])
    s_dict["vector_db_dir"] = str(s_dict["vector_db_dir"])
    return s_dict

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    await db.delete(session)
    await db.commit()
    return {"status": "success"}

@router.delete("/sessions")
async def delete_all_sessions(db: AsyncSession = Depends(get_db)):
    await db.execute(delete(Message))
    await db.execute(delete(Session))
    await db.commit()
    return {"status": "success"}

@router.get("/documents")
async def get_documents(request: Request):
    chunks = getattr(request.app.state, "chunks", [])
    indexed_pdfs = {c.get("document") for c in chunks}
    
    docs = []
    if settings.data_dir.exists():
        import datetime
        for pdf_path in settings.data_dir.glob("*.pdf"):
            filename = pdf_path.name
            title = filename.replace(".pdf", "").replace("_", " ").title()
            # The ingestion pipeline sets chunk["document"] to the title
            status = "active" if title in indexed_pdfs else "processing"
            docs.append({
                "id": filename,
                "filename": filename,
                "title": filename.replace(".pdf", "").replace("_", " ").title(),
                "status": status,
                "created_at": datetime.datetime.fromtimestamp(pdf_path.stat().st_mtime, datetime.timezone.utc).isoformat()
            })
    docs.sort(key=lambda x: x["created_at"], reverse=True)
    return docs

@router.post("/documents")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    file_path = settings.data_dir / file.filename
    
    with open(file_path, "wb") as buffer:
        import shutil
        shutil.copyfileobj(file.file, buffer)
        
    return {"status": "success", "message": "Document uploaded and indexing automatically triggered via file watcher."}

@router.delete("/documents/{filename}")
async def delete_document(filename: str):
    file_path = settings.data_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document not found on disk")
        
    file_path.unlink()
    return {"status": "success", "message": "Document physically deleted. File watcher will automatically rebuild the index."}
