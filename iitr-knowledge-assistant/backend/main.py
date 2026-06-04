from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.ask import router as ask_router
from backend.config import settings
from backend.indexing.build_index import load_index
from backend.logging.analytics import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    logger.info("Loading FAISS index from %s", settings.faiss_index_path)

    try:
        index, chunks = load_index()
        app.state.faiss_index = index
        app.state.chunks = chunks
        app.state.index_loaded = True
        logger.info("Index loaded: %d chunks", len(chunks))
    except FileNotFoundError as exc:
        app.state.faiss_index = None
        app.state.chunks = None
        app.state.index_loaded = False
        logger.warning("Index not loaded: %s", exc)

    yield


app = FastAPI(
    title="IITR Knowledge Assistant",
    description="Institution-wide AI assistant for official IIT Roorkee documents",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ask_router)


@app.get("/health")
def health():
    index_loaded = getattr(app.state, "index_loaded", False)
    chunk_count = len(app.state.chunks) if index_loaded else 0
    return {
        "status": "ok" if index_loaded else "degraded",
        "index_loaded": index_loaded,
        "chunk_count": chunk_count,
        "embedding_model": settings.embedding_model,
        "rerank_model": settings.rerank_model,
        "llm_model": settings.ollama_model,
    }
