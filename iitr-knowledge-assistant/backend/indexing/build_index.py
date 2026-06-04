import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from backend.config import settings
from backend.ingestion.chunker import chunk_pages
from backend.ingestion.metadata import attach_metadata
from backend.ingestion.pdf_loader import extract_pages


def _get_encoder() -> SentenceTransformer:
    return SentenceTransformer(settings.embedding_model)


def ingest_document(pdf_path: Path | None = None) -> list[dict]:
    """Extract, chunk, and enrich a PDF into indexed chunks."""
    path = pdf_path or settings.pdf_path
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    pages = extract_pages(str(path))
    raw_chunks = chunk_pages(pages)
    return attach_metadata(raw_chunks)


def build_and_save_index(
    chunks: list[dict] | None = None,
    pdf_path: Path | None = None,
) -> tuple[faiss.IndexFlatL2, list[dict]]:
    """Build FAISS index from chunks and persist to disk."""
    if chunks is None:
        chunks = ingest_document(pdf_path)

    encoder = _get_encoder()
    texts = [c["text"] for c in chunks]
    embeddings = encoder.encode(texts, show_progress_bar=True)
    embeddings = np.array(embeddings).astype("float32")

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    settings.faiss_index_path.parent.mkdir(parents=True, exist_ok=True)
    settings.chunks_metadata_path.parent.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(settings.faiss_index_path))
    with open(settings.chunks_metadata_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    return index, chunks


def load_index() -> tuple[faiss.IndexFlatL2, list[dict]]:
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
