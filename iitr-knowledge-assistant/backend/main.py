from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.api.routes.ask import router as ask_router
# from backend.api.routes.voice import router as voice_router  # disabled — re-enable when voice is added back
from backend.api.routes.admin import router as admin_router
# from backend.services.voice_service import init_voice_models  # disabled — re-enable when voice is added back
from backend.config import PROJECT_ROOT, settings
from backend.indexing.build_index import load_index
from backend.logging.analytics import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    logger.info(f"USING FAISS PATH: {settings.faiss_index_path}")
    logger.info("Loading FAISS index from %s", settings.faiss_index_path)
    
    app.state.models_loading = True

    try:
        index, chunks = load_index()
        app.state.faiss_index = index
        app.state.chunks = chunks
        app.state.index_loaded = True
        logger.info("Index loaded: %d chunks", len(chunks))

        # Pre-initialize BM25 index
        from backend.retrieval.bm25 import get_bm25_index
        get_bm25_index(chunks)
        logger.info("BM25 index initialized successfully")

    except FileNotFoundError as exc:
        app.state.faiss_index = None
        app.state.chunks = None
        app.state.index_loaded = False
        logger.warning("Index not loaded: %s", exc)

    # Initialize LLM semaphore
    import asyncio
    app.state.llm_semaphore = asyncio.Semaphore(2)

    async def load_hf_models():
        logger.info("Pre-fetching HuggingFace models in background...")
        def _load():
            from backend.retrieval.search import get_encoder
            get_encoder()
            from backend.retrieval.rerank import get_ranker
            get_ranker()
            from backend.query.intent import get_intent_router
            get_intent_router()
        await asyncio.to_thread(_load)
        logger.info("All HuggingFace models initialized successfully")
        app.state.models_loading = False

    asyncio.create_task(load_hf_models())

    yield


from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from backend.api.limiter import limiter

app = FastAPI(
    title="IITR Knowledge Assistant",
    description="Institution-wide AI assistant for official IIT Roorkee documents",
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)

app.include_router(ask_router)
# app.include_router(voice_router)
app.include_router(admin_router)


@app.get("/health")
def health():
    index_loaded = getattr(app.state, "index_loaded", False)
    models_loading = getattr(app.state, "models_loading", False)
    chunk_count = len(app.state.chunks) if index_loaded else 0
    return {
        "status": "ok" if index_loaded and not models_loading else ("loading" if models_loading else "degraded"),
        "index_loaded": index_loaded,
        "models_loading": models_loading,
        "chunk_count": chunk_count,
        "embedding_model": settings.embedding_model,
        "rerank_model": settings.rerank_model,
        "llm_model": settings.ollama_model,
    }


# Serve chat UI on the same port (explicit routes — root StaticFiles breaks POST /ask)
_frontend_dir = PROJECT_ROOT / "frontend"
_FRONTEND_FILES = ("index.html", "script.js", "style.css", "admin.html", "admin.js", "admin.css")


def _serve_frontend_file(name: str):
    path = _frontend_dir / name
    if not path.is_file():
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"{name} not found")
    return FileResponse(path)


if _frontend_dir.is_dir():

    @app.get("/")
    def serve_index():
        return _serve_frontend_file("index.html")

    @app.get("/api-config.js")
    def serve_api_config():
        from fastapi.responses import PlainTextResponse
        api_key_line = f"window.API_KEY = '{settings.api_key}';\n" if settings.api_key else ""
        content = f"window.API_SAME_ORIGIN = true;\nwindow.API_PORT = {settings.api_port};\n{api_key_line}"
        return PlainTextResponse(content, media_type="application/javascript")

    for _name in _FRONTEND_FILES:
        if _name == "index.html":
            continue

        def _make_handler(filename: str):
            def handler():
                return _serve_frontend_file(filename)

            return handler

        app.get(f"/{_name}")(_make_handler(_name))

    @app.get("/ask")
    def ask_get_hint():
        """Browser may open /ask via GET — only POST is valid for questions."""
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url="/", status_code=302)

from fastapi.staticfiles import StaticFiles
raw_data_dir = PROJECT_ROOT / "data" / "raw"
if raw_data_dir.is_dir():
    app.mount("/docs", StaticFiles(directory=str(raw_data_dir)), name="docs")

assets_dir = PROJECT_ROOT / "assets"
if assets_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

@app.get("/favicon.ico")
def favicon():
    from fastapi.responses import FileResponse
    return FileResponse(assets_dir / "favicon.ico")
