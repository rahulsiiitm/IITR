import re

from flashrank import Ranker, RerankRequest

from backend.config import settings

_ranker: Ranker | None = None


def get_ranker() -> Ranker:
    global _ranker
    if _ranker is None:
        _ranker = Ranker()
    return _ranker


def _query_variants(query: str) -> list[str]:
    from backend.query.processor import expand_query_intent
    sub_q = [
        q.strip()
        for q in re.split(r"(?i)\?|\s+and\s+|\s+also\s+|\s+or\s+", query)
        if q.strip()
    ]
    variants = [query, expand_query_intent(query)] + sub_q
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

    ranker = get_ranker()
    all_queries = _query_variants(query)

    passages = [{"id": i, "text": c["chunk"], "meta": c} for i, c in enumerate(candidates)]

    best_scores = [-999.0] * len(candidates)
    for q in all_queries:
        req = RerankRequest(query=q, passages=passages)
        results = ranker.rerank(req)
        for res in results:
            idx = res["id"]
            best_scores[idx] = max(best_scores[idx], float(res["score"]))

    q_lower = query.lower()
    is_epe_query = (
        "epe" in q_lower or "extensive" in q_lower or "professional experience" in q_lower
    )

    for idx, candidate in enumerate(candidates):
        score = best_scores[idx]
        chunk_lower = candidate["chunk"].lower()
        if not is_epe_query and (
            "professional experience" in chunk_lower or re.search(r"\bepe\b", chunk_lower)
        ):
            score -= 10.0
            
        # Unified Search Priority Boost: Give PhD Regulations a slight edge over SOPs (tie-breaker only)
        if candidate.get("doc_type") == "regulation":
            score += 0.02
            
        # SOP Keyword Boost: Ensure extremely specific SOP queries retrieve the exact target SOP
        SOP_BOOSTS = {
            "externally funded": 2.0,
            "efrs": 2.0,
            "mou category": 2.0,
            "reinstatement": 2.0,
            "jrf-srf": 2.0,
            "jrf to srf": 2.0,
            "domestic conference": 2.0,
            "seminar code": 2.0,
            "2-credit seminar": 2.0,
            "2 credit seminar": 2.0,
            "hindi abstract": 2.0,
            "abstract in hindi": 2.0,
            "excellence in doctoral": 2.0,
            "doctoral research award": 2.0,
            "institutional visit": 2.0,
            "thesis submission fee": 2.0,
        }
        
        q_lower = query.lower()
        for kw, boost in SOP_BOOSTS.items():
            if kw in q_lower and kw in chunk_lower:
                score += boost
            
        candidate["rerank_score"] = score

    ranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
    limit = top_k if top_k is not None else len(ranked)
    return ranked[:limit]


def check_confidence(candidates: list[dict], query: str = "") -> bool:
    """Return True if best rerank score exceeds confidence threshold.

    Procedural / process / how-to questions use a relaxed threshold because
    the cross-encoder scores them lower even when the content is relevant.
    """
    if not candidates:
        return False
    best_score = max(c.get("rerank_score", -20) for c in candidates)

    # Relaxed threshold for vague procedural / informational questions
    q = query.lower()
    procedural_keywords = [
        "step", "process", "procedure", "how", "what to do",
        "after admission", "after joining", "joining",
        "follow", "what should", "what must", "what does",
        "guideline", "explain", "describe", "overview",
    ]
    if any(kw in q for kw in procedural_keywords):
        threshold = -6.0  # relaxed: any semantically near-miss chunk is allowed
    else:
        # FlashRank uses positive scores (typically 0.0 to 1.0)
        threshold = 0.0 if settings.confidence_threshold < 0 else settings.confidence_threshold

    return best_score > threshold


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
                expanded.append(chunk_data)
                seen_indices.add(neighbor_idx)

    return expanded
