from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from backend.database import get_db
from backend.models import Session, Message
from backend.config import settings

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
