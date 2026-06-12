import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from backend.config import settings
from backend.ingestion.chunker import chunk_pages
from backend.ingestion.metadata import attach_metadata
from backend.ingestion.pdf_loader import extract_pages


def _get_encoder() -> SentenceTransformer:
    return SentenceTransformer(settings.embedding_model, device="cpu")


def ingest_document(pdf_path: Path, start_id: int = 1) -> list[dict]:
    """Extract, chunk, and enrich a PDF into indexed chunks."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pages = extract_pages(str(pdf_path))
    raw_chunks = chunk_pages(pages)
    return attach_metadata(raw_chunks, filename=pdf_path.name, start_id=start_id)


def build_and_save_index() -> tuple[faiss.IndexFlatIP, list[dict]]:
    """Build FAISS index from all PDFs in data_dir and persist to disk."""
    chunks = []
    start_id = 1
    
    if not settings.data_dir.exists():
        raise FileNotFoundError(f"Data dir not found: {settings.data_dir}")
        
    for pdf_path in settings.data_dir.glob("*.pdf"):
        logger.info(f"Processing: {pdf_path.name}")
        doc_chunks = ingest_document(pdf_path, start_id)
        chunks.extend(doc_chunks)
        start_id += len(doc_chunks)
        
    if not chunks:
        raise ValueError(f"No PDFs found in {settings.data_dir}")

    encoder = _get_encoder()
    texts = [c["text"] for c in chunks]
    embeddings = encoder.encode(texts, show_progress_bar=True)
    embeddings = np.array(embeddings).astype("float32")

    dimension = embeddings.shape[1]

    # Normalize to unit vectors so that inner product == cosine similarity.
    # BGE models are trained with cosine similarity; L2 on raw vectors gives
    # suboptimal ranking.  faiss.normalize_L2 operates in-place.
    faiss.normalize_L2(embeddings)

    index = faiss.IndexFlatIP(dimension)  # Inner Product = Cosine on unit vectors
    index.add(embeddings)

    settings.faiss_index_path.parent.mkdir(parents=True, exist_ok=True)
    settings.chunks_metadata_path.parent.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(settings.faiss_index_path))
    with open(settings.chunks_metadata_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    return index, chunks


def load_index() -> tuple[faiss.IndexFlatIP, list[dict]]:
    """Load persisted FAISS index and chunk metadata."""
    if not settings.faiss_index_path.exists():
        raise FileNotFoundError(
            f"FAISS index not found at {settings.faiss_index_path}. "
            "Run: python scripts/build_index.py"
        )
    if not settings.chunks_metadata_path.exists():
        raise FileNotFoundError(
            f"Chunk metadata not found at {settings.chunks_metadata_path}. "
            "Run: python scripts/build_index.py"
        )

    index = faiss.read_index(str(settings.faiss_index_path))
    with open(settings.chunks_metadata_path, encoding="utf-8") as f:
        chunks = json.load(f)

    return index, chunks
