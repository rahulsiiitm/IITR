import re

from sentence_transformers import CrossEncoder

from backend.config import settings

_cross_encoder: CrossEncoder | None = None


def get_cross_encoder() -> CrossEncoder:
    global _cross_encoder
    if _cross_encoder is None:
        _cross_encoder = CrossEncoder(settings.rerank_model)
    return _cross_encoder


def _query_variants(query: str) -> list[str]:
    sub_q = [
        q.strip()
        for q in re.split(r"(?i)\?|\s+and\s+|\s+also\s+|\s+or\s+", query)
        if q.strip()
    ]
    variants = [query] + sub_q
    all_queries: list[str] = []

    for q in variants:
        if q not in all_queries:
            all_queries.append(q)
        q_lower = q.lower()
        if "iit roorkee" in q_lower or "iitr" in q_lower:
            alt_q = (
                q.replace("IIT Roorkee", "the Institute")
                .replace("IITR", "the Institute")
                .replace("iit roorkee", "the Institute")
                .replace("iitr", "the Institute")
            )
            if alt_q not in all_queries:
                all_queries.append(alt_q)
        elif "institute" in q_lower:
            alt_q = (
                q.replace("the Institute", "IIT Roorkee")
                .replace("Institute", "IIT Roorkee")
                .replace("the institute", "IIT Roorkee")
                .replace("institute", "IIT Roorkee")
            )
            if alt_q not in all_queries:
                all_queries.append(alt_q)

    return all_queries


def rerank(
    query: str,
    candidates: list[dict],
    top_k: int | None = None,
) -> list[dict]:
    """Rerank candidates using cross-encoder relevance scores."""
    if not candidates:
        return []

    cross_encoder = get_cross_encoder()
    all_queries = _query_variants(query)

    best_scores = [-999.0] * len(candidates)
    for q in all_queries:
        pairs = [(q, c["chunk"]) for c in candidates]
        scores = cross_encoder.predict(pairs)
        for idx, score in enumerate(scores):
            best_scores[idx] = max(best_scores[idx], float(score))

    q_lower = query.lower()
    is_epe_query = (
        "epe" in q_lower or "extensive" in q_lower or "professional experience" in q_lower
    )

    for idx, candidate in enumerate(candidates):
        score = best_scores[idx]
        chunk_lower = candidate["chunk"].lower()
        if not is_epe_query and (
            "professional experience" in chunk_lower or "epe" in chunk_lower
        ):
            score -= 10.0
        candidate["rerank_score"] = score

    ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
    limit = top_k if top_k is not None else len(ranked)
    return ranked[:limit]


def check_confidence(candidates: list[dict]) -> bool:
    """Return True if best rerank score exceeds confidence threshold."""
    if not candidates:
        return False
    best_score = max(c.get("rerank_score", -20) for c in candidates)
    return best_score > settings.confidence_threshold


def expand_context(candidates: list[dict], chunks: list[dict]) -> list[dict]:
    """Include neighboring chunks (index ±1) for each candidate."""
    expanded: list[dict] = []
    seen_indices: set[int] = set()

    for candidate in candidates:
        idx = candidate.get("index")
        if idx is None:
            expanded.append(candidate)
            continue

        for neighbor_idx in range(max(0, idx - 1), min(len(chunks), idx + 2)):
            if neighbor_idx not in seen_indices:
                chunk_data = chunks[neighbor_idx].copy()
                chunk_data["chunk"] = chunk_data.get("text", chunk_data.get("chunk", ""))
                if neighbor_idx == idx:
                    chunk_data["rerank_score"] = candidate.get("rerank_score", 0)
                else:
                    chunk_data["rerank_score"] = candidate.get("rerank_score", 0) - 1.0
                expanded.append(chunk_data)
                seen_indices.add(neighbor_idx)

    return expanded
