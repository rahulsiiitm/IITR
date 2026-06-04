import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.config import settings
from backend.generation.llm import ask as generate_answer
from backend.logging.analytics import RequestTimer, log_ask_request
from backend.query.processor import retrieve_candidates, select_reranked_per_page
from backend.query.shortcuts import check_cgpa_gate_shortcut, check_vague_requirements
from backend.retrieval.rerank import check_confidence, expand_context

logger = logging.getLogger(__name__)
router = APIRouter()


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)


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
def ask_question(body: AskRequest, request: Request) -> AskResponse:
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="No question provided")

    timer = RequestTimer()

    vague = check_vague_requirements(question)
    if vague:
        return AskResponse(answer=vague, sources=[])

    shortcut = check_cgpa_gate_shortcut(question)
    if shortcut:
        return AskResponse(
            answer=shortcut["answer"],
            sources=[SourceItem(**s) for s in shortcut["sources"]],
        )

    index, chunks = _get_index_state(request)

    try:
        candidates = retrieve_candidates(question, index, chunks)
        reranked, reranked_raw = select_reranked_per_page(question, candidates)
        expanded = expand_context(reranked, chunks)
        is_confident = check_confidence(expanded)

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

        result = generate_answer(question, expanded)
        response = AskResponse(
            answer=result["answer"],
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
        raise HTTPException(status_code=500, detail=str(exc)) from exc
