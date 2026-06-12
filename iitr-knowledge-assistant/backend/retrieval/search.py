import faiss
from sentence_transformers import SentenceTransformer

from backend.config import settings

BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_encoder: SentenceTransformer | None = None


def get_encoder() -> SentenceTransformer:
    global _encoder
    if _encoder is None:
        _encoder = SentenceTransformer(settings.embedding_model, device="cpu")
    return _encoder


def reciprocal_rank_fusion(
    dense_results: list[dict],
    sparse_results: list[dict],
    k: int = 60,
    top_n: int = 20,
) -> list[dict]:
    """Combine dense and sparse search results using Reciprocal Rank Fusion (RRF)."""
    rrf_scores = {}
    chunk_lookup = {}

    for rank, item in enumerate(dense_results, start=1):
        key = item["chunk_id"]
        chunk_lookup[key] = item
        rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (k + rank))

    for rank, item in enumerate(sparse_results, start=1):
        key = item["chunk_id"]
        if key not in chunk_lookup:
            chunk_lookup[key] = item
        else:
            chunk_lookup[key]["bm25_score"] = item.get("bm25_score")
        rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (k + rank))

    sorted_keys = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

    fused = []
    for key in sorted_keys[:top_n]:
        item = chunk_lookup[key].copy()
        item["rrf_score"] = rrf_scores[key]
        fused.append(item)

    return fused


def search(
    query: str,
    index: faiss.IndexFlatIP,
    chunks: list[dict],
    top_k: int | None = None,
) -> list[dict]:
    """Retrieve candidate chunks using hybrid dense (FAISS) and sparse (BM25) search with RRF."""
    k_target = top_k or settings.top_k
    k_fetch = k_target * 2

    # 1. Dense Search (FAISS)
    prefixed_query = query if query.startswith(BGE_QUERY_PREFIX) else f"{BGE_QUERY_PREFIX}{query}"
    encoder = get_encoder()
    query_embedding = encoder.encode([prefixed_query]).astype("float32")
    # Normalize to unit vector — required for cosine similarity via IndexFlatIP
    faiss.normalize_L2(query_embedding)
    distances, indices = index.search(query_embedding, k_fetch)

    dense_results = []
    for i, idx in enumerate(indices[0]):
        if idx < len(chunks):
            chunk = chunks[idx]
            dense_results.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "chunk": chunk["text"],
                    "page": chunk["page"],
                    "document": chunk["document"],
                    "doc_type": chunk.get("doc_type", "sop"),
                    "full_page": chunk.get("full_page", chunk["text"]),
                    "l2_score": float(distances[0][i]),
                    "index": chunk.get("index", idx),
                }
            )

    # 2. Sparse Search (BM25)
    from backend.retrieval.bm25 import search_bm25
    sparse_results = search_bm25(query, chunks, top_k=k_fetch)

    # 3. Reciprocal Rank Fusion
    fused_results = reciprocal_rank_fusion(
        dense_results=dense_results,
        sparse_results=sparse_results,
        k=60,
        top_n=k_target
    )

    return fused_results
