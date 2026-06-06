import re

from backend.config import settings
from backend.retrieval.search import search

QUERY_EXPANSIONS = {
    "candidacy": "coursework comprehensive examination research proposal obtaining candidacy",
    "thesis submission": "thesis submission final src examiner thesis",
    "gate exemption": "gate exempted national level test",
    "patent": "patent filed published thesis work equivalent published paper peer reviewed journal",
    "publication": "publication paper peer reviewed journal thesis work patent equivalent",
    # Post-admission / joining process → R.2 (pages 23-24)
    "after admission": "joining process supervisor SRC registration report head department",
    "steps after": "joining process supervisor SRC registration report head department",
    "after joining": "joining process supervisor SRC registration report head department",
    "first step": "joining process supervisor SRC registration report head department",
    "what to do": "joining process supervisor SRC registration report head department",
    "process after": "joining process supervisor SRC registration report head department",
    "steps to follow": "joining process supervisor SRC registration report head department",
    "joining": "joining process supervisor SRC registration report head department",
    # Admission qualifications (Page 15)
    "minimum cgpa": "minimum qualifications admission eligibility criteria qualifying degree",
    "cgpa required": "minimum qualifications admission eligibility criteria qualifying degree",
    "percentage required": "minimum qualifications admission eligibility criteria qualifying degree",
    "eligible for direct": "minimum qualifications admission eligibility criteria qualifying degree gate exemption",
    "direct phd": "minimum qualifications admission eligibility criteria qualifying degree gate exemption",
    # Working period / thesis submission duration (Page 34)
    "working period": "minimum working period thesis submission candidacy duration R.8",
    "minimum working": "minimum working period thesis submission candidacy duration R.8",
    # Performance Monitoring / Warnings / Unsatisfactory Progress (Page 32)
    "warning": "warning unsatisfactory progress report academic affairs office R.8",
    "warnings": "warning unsatisfactory progress report academic affairs office R.8",
    "unsatisfactory": "unsatisfactory progress report academic affairs office academic registration cancelled units R.8",
    # Comprehensive Examination Attempts (Page 31)
    "attempt": "comprehensive examination attempts twice maximum attempts candidate avail to clear r.7",
    "attempts": "comprehensive examination attempts twice maximum attempts candidate avail to clear r.7",
    "twice": "comprehensive examination attempts twice maximum attempts candidate avail to clear r.7",
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
    """Rerank all candidates and keep best chunks (allowing multiple per page)."""
    from backend.retrieval.rerank import rerank

    sub_questions = split_sub_questions(question)
    k_val = (
        settings.rerank_top_k_multi
        if len(sub_questions) > 1
        else settings.rerank_top_k
    )

    reranked_raw = rerank(question, candidates, top_k=len(candidates))

    selected: list[dict] = []
    for c in reranked_raw:
        # Drop subsequent candidates with scores below the confidence threshold to filter out noise
        if len(selected) > 0 and c.get("rerank_score", 0) < settings.confidence_threshold:
            continue
        selected.append(c)

    return selected[:k_val], reranked_raw
