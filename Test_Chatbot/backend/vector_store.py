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

    # Support query expansion and sub-question splitting in reranker
    import re
    sub_q = [q.strip() for q in re.split(r'(?i)\?|\s+and\s+|\s+also\s+|\s+or\s+', query) if q.strip()]
    q_variants = [query] + sub_q

    all_queries = []
    for q in q_variants:
        if q not in all_queries:
            all_queries.append(q)
        q_lower = q.lower()
        if "iit roorkee" in q_lower or "iitr" in q_lower:
            alt_q = q.replace("IIT Roorkee", "the Institute").replace("IITR", "the Institute").replace("iit roorkee", "the Institute").replace("iitr", "the Institute")
            if alt_q not in all_queries:
                all_queries.append(alt_q)
        elif "institute" in q_lower:
            alt_q = q.replace("the Institute", "IIT Roorkee").replace("Institute", "IIT Roorkee").replace("the institute", "IIT Roorkee").replace("institute", "IIT Roorkee")
            if alt_q not in all_queries:
                all_queries.append(alt_q)

    # Score candidates against all query variants, keeping the maximum score
    best_scores = [-999.0] * len(candidates)
    for q in all_queries:
        pairs = [(q, c["chunk"]) for c in candidates]
        scores = cross_encoder.predict(pairs)
        for idx, score in enumerate(scores):
            best_scores[idx] = max(best_scores[idx], float(score))

    # Check if query targets EPE / Extensive Professional Experience
    q_lower = query.lower()
    is_epe_query = "epe" in q_lower or "extensive" in q_lower or "professional experience" in q_lower

    # Attach scores and sort by relevance (highest first)
    for idx, candidate in enumerate(candidates):
        score = best_scores[idx]
        chunk_lower = candidate["chunk"].lower()
        # Heavy penalty if the chunk is about EPE but query is not
        if not is_epe_query and ("professional experience" in chunk_lower or "epe" in chunk_lower):
            score -= 10.0
        candidate["rerank_score"] = score

    ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
    return ranked[:top_k]


def check_confidence(candidates):
    """Check if the best candidate passes the confidence threshold.
    
    Returns:
        True if results are confident enough to use, False otherwise
    """
    if not candidates:
        return False

    # Check the maximum score in the candidates list with a threshold of 1.0
    best_score = max(c.get("rerank_score", -20) for c in candidates)
    return best_score > 1.0


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

