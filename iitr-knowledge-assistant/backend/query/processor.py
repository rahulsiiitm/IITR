import re

from backend.config import settings
from backend.retrieval.search import search

QUERY_EXPANSIONS = {
    "candidacy": "coursework comprehensive examination research proposal obtaining candidacy",
    "thesis submission": "thesis submission final src examiner thesis",
    "gate exemption": "gate exempted national level test",
}


def split_sub_questions(question: str) -> list[str]:
    return [
        q.strip()
        for q in re.split(r"(?i)\?|\s+and\s+|\s+also\s+|\s+or\s+", question)
        if q.strip()
    ]


def expand_query_intent(query: str) -> str:
    expanded = query
    q_lower = query.lower()
    for key, expansion in QUERY_EXPANSIONS.items():
        if key in q_lower:
            expanded += " " + expansion
    return expanded


def search_with_expansion(
    query: str,
    index,
    chunks: list[dict],
    top_k: int,
) -> list[dict]:
    """Search with intent expansion and IIT Roorkee alt-query handling."""
    q_expanded = expand_query_intent(query)
    results = search(q_expanded, index, chunks, top_k=top_k)

    q_lower = q_expanded.lower()
    if "iit roorkee" in q_lower or "iitr" in q_lower:
        alt_q = (
            q_expanded.replace("IIT Roorkee", "the Institute")
            .replace("IITR", "the Institute")
            .replace("iit roorkee", "the Institute")
            .replace("iitr", "the Institute")
        )
        alt_results = search(alt_q, index, chunks, top_k=top_k)
        seen = {(r["page"], r["chunk"]) for r in results}
        for r in alt_results:
            if (r["page"], r["chunk"]) not in seen:
                results.append(r)

    return results


def retrieve_candidates(
    question: str,
    index,
    chunks: list[dict],
) -> list[dict]:
    """Retrieve candidate chunks for a question (handles compound questions)."""
    sub_questions = split_sub_questions(question)

    if len(sub_questions) <= 1:
        return search_with_expansion(question, index, chunks, top_k=settings.top_k)

    all_candidates: list[dict] = []
    seen_keys: set[tuple] = set()

    for sq in sub_questions:
        candidates = search_with_expansion(
            sq, index, chunks, top_k=settings.subquestion_top_k
        )
        for c in candidates:
            key = (c["page"], c["chunk"])
            if key not in seen_keys:
                all_candidates.append(c)
                seen_keys.add(key)

    return all_candidates


def select_reranked_per_page(
    question: str,
    candidates: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Rerank all candidates and keep best chunk per page."""
    from backend.retrieval.rerank import rerank

    sub_questions = split_sub_questions(question)
    k_val = (
        settings.rerank_top_k_multi
        if len(sub_questions) > 1
        else settings.rerank_top_k
    )

    reranked_raw = rerank(question, candidates, top_k=len(candidates))

    selected: list[dict] = []
    seen_pages: set[int] = set()
    for c in reranked_raw:
        if c["page"] not in seen_pages:
            selected.append(c)
            seen_pages.add(c["page"])

    return selected[:k_val], reranked_raw
