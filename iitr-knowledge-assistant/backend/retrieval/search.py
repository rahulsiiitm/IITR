import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from backend.config import settings

BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_encoder: SentenceTransformer | None = None


def get_encoder() -> SentenceTransformer:
    global _encoder
    if _encoder is None:
        _encoder = SentenceTransformer(settings.embedding_model)
    return _encoder


def search(
    query: str,
    index: faiss.IndexFlatL2,
    chunks: list[dict],
    top_k: int | None = None,
) -> list[dict]:
    """Retrieve top-k chunks via FAISS L2 search."""
    k = top_k or settings.top_k
    prefixed_query = query if query.startswith(BGE_QUERY_PREFIX) else f"{BGE_QUERY_PREFIX}{query}"

    encoder = get_encoder()
    query_embedding = encoder.encode([prefixed_query]).astype("float32")
    distances, indices = index.search(query_embedding, k)

    results: list[dict] = []
    for i, idx in enumerate(indices[0]):
        if idx < len(chunks):
            chunk = chunks[idx]
            results.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "chunk": chunk["text"],
                    "page": chunk["page"],
                    "document": chunk["document"],
                    "full_page": chunk.get("full_page", chunk["text"]),
                    "l2_score": float(distances[0][i]),
                    "index": chunk.get("index", idx),
                }
            )

    return results
