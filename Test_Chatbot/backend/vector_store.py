import faiss
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder

# Load models once at import time
bi_encoder = SentenceTransformer("BAAI/bge-small-en-v1.5")
cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

# Confidence threshold — L2 distance above this means "not relevant"
# For normalized embeddings: L2² ≈ 2(1 - cosine_sim)
# L2 of 1.3 ≈ cosine_sim of 0.15 (very low relevance)
CONFIDENCE_THRESHOLD = 1.3


def build_index(chunks):
    """Build a FAISS index from text chunks.
    
    Args:
        chunks: List of dicts [{"chunk": "...", "page": 1}, ...]
    
    Returns:
        (faiss_index, chunks) - the index and the original chunks for lookup
    """
    texts = [c["chunk"] for c in chunks]
    embeddings = bi_encoder.encode(texts, show_progress_bar=True)
    embeddings = np.array(embeddings).astype("float32")

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    return index, chunks


def search(query, index, chunks, top_k=10):
    # Prepend BGE query instruction prefix for asymmetric search
    prefix = "Represent this sentence for searching relevant passages: "
    prefixed_query = query if query.startswith(prefix) else f"{prefix}{query}"
    query_embedding = bi_encoder.encode([prefixed_query]).astype("float32")
    distances, indices = index.search(query_embedding, top_k)

    results = []
    for i, idx in enumerate(indices[0]):
        if idx < len(chunks):
            results.append({
                "chunk": chunks[idx]["chunk"],
                "page": chunks[idx]["page"],
                "full_page": chunks[idx].get("full_page", ""),
                "l2_score": float(distances[0][i]),
                "index": idx
            })

    return results


def rerank(query, candidates, top_k=3):
    """Rerank candidates using a cross-encoder for better precision.
    
    Cross-encoder scores query-chunk pairs jointly, which is more accurate
    than bi-encoder similarity for determining true relevance.
    
    Args:
        query: User question string
        candidates: List of dicts from search()
        top_k: Number of best results to keep after reranking
    
    Returns:
        List of dicts sorted by cross-encoder relevance (highest first)
    """
    if not candidates:
        return []

    # Support query expansion in reranker to handle entity/term mismatch
    q_lower = query.lower()
    alt_queries = [query]
    if "iit roorkee" in q_lower or "iitr" in q_lower:
        alt_q = query.replace("IIT Roorkee", "the Institute").replace("IITR", "the Institute").replace("iit roorkee", "the Institute").replace("iitr", "the Institute")
        alt_queries.append(alt_q)
    elif "institute" in q_lower:
        alt_q = query.replace("the Institute", "IIT Roorkee").replace("Institute", "IIT Roorkee").replace("the institute", "IIT Roorkee").replace("institute", "IIT Roorkee")
        alt_queries.append(alt_q)

    # Score candidates against all generated query variants, keeping the maximum score
    best_scores = [-999.0] * len(candidates)
    for q in alt_queries:
        pairs = [(q, c["chunk"]) for c in candidates]
        scores = cross_encoder.predict(pairs)
        for idx, score in enumerate(scores):
            best_scores[idx] = max(best_scores[idx], float(score))

    # Attach scores and sort by relevance (highest first)
    for idx, candidate in enumerate(candidates):
        candidate["rerank_score"] = best_scores[idx]

    ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
    return ranked[:top_k]


def check_confidence(candidates):
    """Check if the best candidate passes the confidence threshold.
    
    Returns:
        True if results are confident enough to use, False otherwise
    """
    if not candidates:
        return False

    # Use rerank_score — cross-encoder scores can be strongly negative, -10 is a safer cutoff
    best_score = candidates[0].get("rerank_score", -20)
    return best_score > -10


def expand_context(candidates, chunks):
    """Include preceding and succeeding chunks (idx-1 and idx+1) for each candidate chunk.
    
    Args:
        candidates: List of reranked candidates
        chunks: Original complete chunk list
    
    Returns:
        Expanded list of chunks preserving rerank score
    """
    expanded = []
    seen_indices = set()
    for c in candidates:
        idx = c.get("index")
        if idx is None:
            expanded.append(c)
            continue
            
        for neighbor_idx in range(max(0, idx - 1), min(len(chunks), idx + 2)):
            if neighbor_idx not in seen_indices:
                chunk_data = chunks[neighbor_idx].copy()
                # If it's the target chunk, preserve rerank score, else degrade slightly
                if neighbor_idx == idx:
                    chunk_data["rerank_score"] = c.get("rerank_score", 0)
                else:
                    chunk_data["rerank_score"] = c.get("rerank_score", 0) - 1.0
                expanded.append(chunk_data)
                seen_indices.add(neighbor_idx)
                
    return expanded

