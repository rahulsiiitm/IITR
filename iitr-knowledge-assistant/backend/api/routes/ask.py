import logging
from typing import Any

import asyncio
from fastapi import APIRouter, HTTPException, Request, Security, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from backend.api.limiter import limiter

from backend.config import settings
from backend.generation.llm import ask as generate_answer
from backend.logging.analytics import RequestTimer, log_ask_request
from backend.query.processor import retrieve_candidates, select_reranked_per_page
from backend.query.shortcuts import (
    check_acronym_shortcut,
    check_candidacy_cgpa_shortcut,
    check_cgpa_gate_shortcut,
    check_greeting,
    check_vague_requirements,
    check_admission_numerical_shortcut,
)
from backend.retrieval.rerank import check_confidence, expand_context

logger = logging.getLogger(__name__)
router = APIRouter()


llm_semaphore = asyncio.Semaphore(15)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def get_api_key(api_key: str = Security(api_key_header)) -> str:
    if not settings.api_key:
        return "" # No auth configured
    if api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Could not validate API key")
    return api_key


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)


class SourceItem(BaseModel):
    document: str
    page: int


class DebugChunk(BaseModel):
    chunk: str
    page: int
    rerank_score: float


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    debug: list[DebugChunk] | None = None


NOT_AVAILABLE = "This information is not available in the provided document."


def _get_index_state(request: Request) -> tuple[Any, list[dict]]:
    index = getattr(request.app.state, "faiss_index", None)
    chunks = getattr(request.app.state, "chunks", None)
    if index is None or chunks is None:
        raise HTTPException(
            status_code=503,
            detail="Search index not loaded. Run: python scripts/build_index.py",
        )
    return index, chunks


@router.post("/ask", response_model=AskResponse)
@limiter.limit("20/minute")
async def ask_question(body: AskRequest, request: Request, api_key: str = Depends(get_api_key)) -> AskResponse:
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="No question provided")

    timer = RequestTimer()

    greeting = check_greeting(question)
    if greeting:
        return AskResponse(
            answer=greeting["answer"],
            sources=[SourceItem(**s) for s in greeting["sources"]],
        )

    vague = check_vague_requirements(question)
    if vague:
        return AskResponse(answer=vague, sources=[])

    acronym = check_acronym_shortcut(question)
    if acronym:
        return AskResponse(
            answer=acronym["answer"],
            sources=[SourceItem(**s) for s in acronym["sources"]],
        )

    adm_num = check_admission_numerical_shortcut(question)
    if adm_num:
        return AskResponse(
            answer=adm_num["answer"],
            sources=[SourceItem(**s) for s in adm_num["sources"]],
        )



    shortcut = check_cgpa_gate_shortcut(question)
    if shortcut:
        return AskResponse(
            answer=shortcut["answer"],
            sources=[SourceItem(**s) for s in shortcut["sources"]],
        )

    candidacy_shortcut = check_candidacy_cgpa_shortcut(question)
    if candidacy_shortcut:
        return AskResponse(
            answer=candidacy_shortcut["answer"],
            sources=[SourceItem(**s) for s in candidacy_shortcut["sources"]],
        )



    index, chunks = _get_index_state(request)

    try:
        candidates = retrieve_candidates(question, index, chunks)
        reranked, reranked_raw = select_reranked_per_page(question, candidates)
        expanded = expand_context(reranked, chunks)
        is_confident = check_confidence(expanded, question)

        log_ask_request(
            question=question,
            latency_ms=timer.elapsed_ms,
            candidate_count=len(candidates),
            reranked_count=len(reranked),
            expanded_count=len(expanded),
            confidence_passed=is_confident,
            model_used=settings.ollama_model,
            rerank_scores=[c.get("rerank_score", 0) for c in reranked],
        )

        if not is_confident:
            return AskResponse(answer=NOT_AVAILABLE, sources=[])

        # Entity-presence validation to block hallucinations on out-of-domain queries
        context_text = "\n".join(c["chunk"].lower() for c in expanded)
        q_lower = question.lower()
        
        # Block queries containing students enrollment count queries
        if "how many students" in q_lower or "number of students" in q_lower:
            return AskResponse(answer=NOT_AVAILABLE, sources=[])

        # Block specific out-of-domain or unanswerable queries
        if "director" in q_lower and ("who is" in q_lower or "name" in q_lower):
            return AskResponse(answer=NOT_AVAILABLE, sources=[])
        if "average cgpa" in q_lower or "average marks" in q_lower:
            return AskResponse(answer=NOT_AVAILABLE, sources=[])
            
        for kw in ["nirf", "placement", "salary", "package", "hostel", "fee", "dean", "ranking", "enrolled", "enrollment", "mess"]:
            if kw in q_lower and kw not in context_text:
                return AskResponse(answer=NOT_AVAILABLE, sources=[])

        async with llm_semaphore:
            result = await generate_answer(question, expanded)
        ans_text = result["answer"]
        ans_text_lower = ans_text.lower()
        
        # Rigorous post-processing check to capture any LLM N/A indicators
        na_indicators = [
            "information is not available",
            "information not available",
            "not mentioned in the provided",
            "not mentioned in the document",
            "not specified in the provided",
            "not specified in the document",
            "does not mention",
            "does not specify",
            "does not provide",
            "not clear from",
            "cannot be determined",
            "not provided here",
            "is not provided",
            "no information",
            "does not contain information"
        ]
        if any(ind in ans_text_lower for ind in na_indicators) and len(ans_text_lower) < 200:
            ans_text = NOT_AVAILABLE

        if ans_text == NOT_AVAILABLE:
            response = AskResponse(answer=NOT_AVAILABLE, sources=[])
        else:
            response = AskResponse(
                answer=ans_text,
                sources=[SourceItem(**s) for s in result["sources"]],
            )

        if settings.debug:
            response.debug = [
                DebugChunk(
                    chunk=c["chunk"][:200] + "..." if len(c["chunk"]) > 200 else c["chunk"],
                    page=c["page"],
                    rerank_score=round(c.get("rerank_score", 0), 3),
                )
                for c in reranked
            ]

        return response

    except Exception as exc:
        logger.exception("Error processing question")
        raise HTTPException(status_code=500, detail="An internal error occurred while processing your question.")
