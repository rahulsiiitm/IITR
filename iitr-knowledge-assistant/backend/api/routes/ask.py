import logging
from typing import Any

import asyncio
import re
import uuid
from fastapi import APIRouter, HTTPException, Request, Security, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from backend.api.limiter import limiter
from backend.config import settings

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import get_db
from backend.models import Session, Message
import json

from fastapi.responses import StreamingResponse
from backend.generation.llm import extract_evidence, generate_from_evidence, stream_answer_from_evidence, _format_sources, synthesize_evidence
from backend.generation.rewriter import rewrite_query
from backend.logging.analytics import RequestTimer, log_ask_request
from backend.query.processor import retrieve_candidates, select_reranked_per_page
from backend.query.shortcuts import (
    check_acronym_shortcut,
    check_candidacy_cgpa_shortcut,
    check_cgpa_gate_shortcut,
    check_vague_requirements,
    check_admission_numerical_shortcut,
)
from backend.retrieval.rerank import check_confidence, expand_context

logger = logging.getLogger(__name__)
router = APIRouter()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def get_api_key(api_key: str = Security(api_key_header)) -> str:
    if not settings.api_key:
        return "" # No auth configured
    if api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Could not validate API key")
    return api_key


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    session_id: str | None = None


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
    session_id: str | None = None


NOT_AVAILABLE = "The regulations do not explicitly state this."


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
async def ask_question(body: AskRequest, request: Request, api_key: str = Depends(get_api_key), db: AsyncSession = Depends(get_db)) -> AskResponse:
    if getattr(request.app.state, "models_loading", False):
        raise HTTPException(status_code=503, detail="Models are still downloading/initializing. Please try again in a few moments.")

    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="No question provided")

    session_id = body.session_id
    if session_id:
        db_session = await db.get(Session, session_id)
        if not db_session:
            db_session = Session(id=session_id)
            db.add(db_session)
            await db.commit()
    else:
        db_session = Session(id=str(uuid.uuid4()))
        db.add(db_session)
        await db.commit()
        session_id = db_session.id

    result = await db.execute(select(Message).where(Message.session_id == session_id).order_by(Message.created_at))
    db_messages = result.scalars().all()
    history = [{"role": msg.role, "content": msg.content} for msg in db_messages[-10:]]

    timer = RequestTimer()

    async def make_response(ans: str, srcs: list) -> AskResponse:
        user_msg = Message(session_id=session_id, role="user", content=question)
        asst_msg = Message(session_id=session_id, role="assistant", content=ans, sources=[s.model_dump() for s in srcs])
        db.add_all([user_msg, asst_msg])
        await db.commit()
        return AskResponse(answer=ans, sources=srcs, session_id=session_id)


    vague = check_vague_requirements(question)
    if vague:
        return await make_response(vague, [])

    search_queries = await rewrite_query(question, history)
    query_for_intent = search_queries[0] if search_queries else question

    # === Pre-Flight Intent Routing ===
    from backend.query.intent import get_intent_router
    from backend.generation.llm import generate_conversational
    
    router_instance = get_intent_router()
    intent = router_instance.classify(question)
    
    if intent == "out_of_domain":
        return await make_response(NOT_AVAILABLE, [])
    elif intent == "conversational":
        async with request.app.state.llm_semaphore:
            ans = await generate_conversational(question, history)
        return await make_response(ans, [])
    # =================================

    acronym = check_acronym_shortcut(question)
    if acronym:
        return await make_response(acronym["answer"], [SourceItem(**s) for s in acronym["sources"]])

    shortcut = check_cgpa_gate_shortcut(question)
    if shortcut:
        return await make_response(shortcut["answer"], [SourceItem(**s) for s in shortcut["sources"]])

    adm_num = check_admission_numerical_shortcut(question)
    if adm_num:
        return await make_response(adm_num["answer"], [SourceItem(**s) for s in adm_num["sources"]])

    candidacy_shortcut = check_candidacy_cgpa_shortcut(question)
    if candidacy_shortcut:
        return await make_response(candidacy_shortcut["answer"], [SourceItem(**s) for s in candidacy_shortcut["sources"]])



    index, chunks = _get_index_state(request)

    try:
        logger.info("--- OPTIMIZED SEARCH QUERIES ---")
        for i, sq in enumerate(search_queries, 1):
            logger.info(f"  {i}. {sq}")
        logger.info("--------------------------------")

        all_expanded = []
        all_evidence = []
        seen_texts = set()

        # Dynamic evidence window: give each sub-query more chunks when there
        # are fewer sub-queries so multi-section answers aren't truncated.
        # With many sub-queries, keep it tight to avoid overflowing the extractor.
        num_queries = len(search_queries)
        if num_queries == 1:
            evidence_top_k = 4   # single focused question → rich context
        elif num_queries == 2:
            evidence_top_k = 3   # two-parter → moderate context each
        else:
            evidence_top_k = 2   # many sub-queries → stay lean per query

        # Hard character budget: never send more than ~6000 chars to the
        # extractor regardless of chunk count (keeps latency predictable).
        EVIDENCE_CHAR_BUDGET = 6_000

        for q in search_queries:
            candidates = retrieve_candidates(q, index, chunks)
            reranked, _ = select_reranked_per_page(q, candidates)
            expanded = expand_context(reranked, chunks)

            for chunk in expanded:
                chunk_text = chunk.get("chunk", "")
                if chunk_text not in seen_texts:
                    seen_texts.add(chunk_text)
                    all_expanded.append(chunk)

            # Select top-k chunks for this sub-query and apply char budget
            evidence_chunks = reranked[:evidence_top_k]
            total_chars = sum(len(c.get("chunk", "")) for c in evidence_chunks)
            if total_chars > EVIDENCE_CHAR_BUDGET:
                # Trim the last chunks until we're within budget
                trimmed, budget_used = [], 0
                for c in evidence_chunks:
                    c_len = len(c.get("chunk", ""))
                    if budget_used + c_len > EVIDENCE_CHAR_BUDGET:
                        break
                    trimmed.append(c)
                    budget_used += c_len
                evidence_chunks = trimmed or evidence_chunks[:1]  # always keep at least 1

            evidence_text = await extract_evidence(q, evidence_chunks)
            if evidence_text and "NO_EVIDENCE" not in evidence_text.upper():
                all_evidence.append(evidence_text)

        all_expanded = sorted(all_expanded, key=lambda c: c.get("page", 0))
        
        merged_evidence = "NO_EVIDENCE"
        if all_evidence:
            async with request.app.state.llm_semaphore:
                merged_evidence = await synthesize_evidence(question, all_evidence)
        
        # Precisely identify which chunks were actually quoted in the extracted evidence
        used_chunks = []
        if merged_evidence != "NO_EVIDENCE":
            ev_clean = re.sub(r'\s+', '', merged_evidence.lower())
            for c in all_expanded:
                chunk_clean = re.sub(r'\s+', '', c.get("chunk", "").lower())
                is_used = False
                if len(chunk_clean) < 40:
                    if chunk_clean in ev_clean: is_used = True
                else:
                    for i in range(0, len(chunk_clean) - 40, 20):
                        if chunk_clean[i:i+40] in ev_clean:
                            is_used = True
                            break
                if is_used:
                    used_chunks.append(c)
        
        # Fallback to the top candidate if sliding window misses (e.g. LLM rephrased)
        if not used_chunks and all_expanded and merged_evidence != "NO_EVIDENCE":
            used_chunks = [all_expanded[0]]
            
        sources = _format_sources(used_chunks)

        is_confident = check_confidence(all_expanded, question)

        log_ask_request(
            question=question,
            latency_ms=timer.elapsed_ms,
            candidate_count=len(all_expanded),
            reranked_count=len(all_expanded),
            expanded_count=len(all_expanded),
            confidence_passed=is_confident,
            model_used=settings.ollama_model,
            rerank_scores=[c.get("rerank_score", 0) for c in all_expanded],
        )

        if not is_confident:
            return await make_response(NOT_AVAILABLE, [])



        async with request.app.state.llm_semaphore:
            result = await generate_from_evidence(question, merged_evidence, all_expanded, history)
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
            "does not contain information",
            "the regulations do not explicitly state this",
            "regulations do not explicitly state this",
        ]
        if any(ind in ans_text_lower for ind in na_indicators):
            ans_text = NOT_AVAILABLE

        if ans_text == NOT_AVAILABLE:
            response = await make_response(NOT_AVAILABLE, [])
        else:
            response = await make_response(
                ans_text,
                [SourceItem(**s) for s in sources],
            )

        # Always include debug info with full chunks so the user can see exactly what was retrieved
        response.debug = [
            DebugChunk(
                chunk=c["chunk"],
                page=c["page"],
                rerank_score=round(c.get("rerank_score", 0), 3),
            )
            for c in all_expanded
        ]

        return response

    except Exception:
        logger.exception("Error processing question")
        raise HTTPException(status_code=500, detail="An internal error occurred while processing your question.")


# ── Streaming endpoint (/ask/stream) ──────────────────────────────────────────
# The retrieval + evidence pipeline runs synchronously first; only the final
# answer generation streams token-by-token via Server-Sent Events.

@router.post("/ask/stream")
@limiter.limit("20/minute")
async def ask_stream(
    body: AskRequest,
    request: Request,
    api_key: str = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    if getattr(request.app.state, "models_loading", False):
        raise HTTPException(status_code=503, detail="Models are still downloading/initializing. Please try again in a few moments.")

    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="No question provided")

    session_id = body.session_id
    if session_id:
        db_session = await db.get(Session, session_id)
        if not db_session:
            db_session = Session(id=session_id)
            db.add(db_session)
            await db.commit()
    else:
        db_session = Session(id=str(uuid.uuid4()))
        db.add(db_session)
        await db.commit()
        session_id = db_session.id

    result = await db.execute(select(Message).where(Message.session_id == session_id).order_by(Message.created_at))
    db_messages = result.scalars().all()
    history = [{"role": msg.role, "content": msg.content} for msg in db_messages[-10:]]

    # Run the full retrieval + evidence pipeline before opening the stream
    index, chunks = _get_index_state(request)

    async def _pipeline_then_stream():
        """Async generator that first runs the full pipeline, then streams the answer."""
        try:
            search_queries = await rewrite_query(question, history)
            query_for_intent = search_queries[0] if search_queries else question

            # ── Intent Router (Conversational/Out of Domain) ─────────────────
            from backend.query.intent import get_intent_router
            from backend.generation.llm import generate_conversational
            
            router_instance = get_intent_router()
            intent = router_instance.classify(question)
            
            if intent == "out_of_domain":
                ans = NOT_AVAILABLE
                db.add_all([
                    Message(session_id=session_id, role="user", content=question),
                    Message(session_id=session_id, role="assistant", content=ans, sources=[]),
                ])
                await db.commit()
                yield f"data: {json.dumps({'type': 'token', 'content': ans})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'sources': [], 'session_id': session_id})}\n\n"
                return
            elif intent == "conversational":
                ans = await generate_conversational(question, history)
                db.add_all([
                    Message(session_id=session_id, role="user", content=question),
                    Message(session_id=session_id, role="assistant", content=ans, sources=[]),
                ])
                await db.commit()
                yield f"data: {json.dumps({'type': 'token', 'content': ans})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'sources': [], 'session_id': session_id})}\n\n"
                return

            # ── Shortcuts (instant responses) ────────────────────────────────
            for check_fn in [
                lambda q: check_acronym_shortcut(q),
                lambda q: check_cgpa_gate_shortcut(q),
                lambda q: check_admission_numerical_shortcut(q),
                lambda q: check_candidacy_cgpa_shortcut(q),
            ]:
                result = check_fn(question)
                if result:
                    ans = result["answer"] if isinstance(result, dict) else result
                    srcs = result.get("sources", []) if isinstance(result, dict) else []
                    # Save to DB
                    db.add_all([
                        Message(session_id=session_id, role="user", content=question),
                        Message(session_id=session_id, role="assistant", content=ans, sources=srcs),
                    ])
                    await db.commit()
                    yield f"data: {json.dumps({'type': 'token', 'content': ans})}\n\n"
                    yield f"data: {json.dumps({'type': 'done', 'sources': srcs, 'session_id': session_id})}\n\n"
                    return

            vague = check_vague_requirements(question)
            if vague:
                db.add_all([
                    Message(session_id=session_id, role="user", content=question),
                    Message(session_id=session_id, role="assistant", content=vague, sources=[]),
                ])
                await db.commit()
                yield f"data: {json.dumps({'type': 'token', 'content': vague})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'sources': [], 'session_id': session_id})}\n\n"
                return

            # ── Retrieval + evidence (blocking, before stream opens) ─────────
            num_queries = len(search_queries)
            evidence_top_k = 4 if num_queries == 1 else (3 if num_queries == 2 else 2)
            EVIDENCE_CHAR_BUDGET = 6_000

            all_expanded, all_evidence, seen_texts = [], [], set()

            for q in search_queries:
                candidates = retrieve_candidates(q, index, chunks)
                reranked, _ = select_reranked_per_page(q, candidates)
                expanded = expand_context(reranked, chunks)

                for chunk in expanded:
                    t = chunk.get("chunk", "")
                    if t not in seen_texts:
                        seen_texts.add(t)
                        all_expanded.append(chunk)

                ev_chunks = reranked[:evidence_top_k]
                if sum(len(c.get("chunk", "")) for c in ev_chunks) > EVIDENCE_CHAR_BUDGET:
                    trimmed, used = [], 0
                    for c in ev_chunks:
                        cl = len(c.get("chunk", ""))
                        if used + cl > EVIDENCE_CHAR_BUDGET:
                            break
                        trimmed.append(c); used += cl
                    ev_chunks = trimmed or ev_chunks[:1]

                ev = await extract_evidence(q, ev_chunks)
                if ev and "NO_EVIDENCE" not in ev.upper():
                    all_evidence.append(ev)

            all_expanded = sorted(all_expanded, key=lambda c: c.get("page", 0))
            merged_evidence = "NO_EVIDENCE"
            if all_evidence:
                async with request.app.state.llm_semaphore:
                    merged_evidence = await synthesize_evidence(question, all_evidence)
            
            # Precisely identify which chunks were actually quoted in the extracted evidence
            used_chunks = []
            if merged_evidence != "NO_EVIDENCE":
                ev_clean = re.sub(r'\s+', '', merged_evidence.lower())
                for c in all_expanded:
                    chunk_clean = re.sub(r'\s+', '', c.get("chunk", "").lower())
                    is_used = False
                    if len(chunk_clean) < 40:
                        if chunk_clean in ev_clean: is_used = True
                    else:
                        for i in range(0, len(chunk_clean) - 40, 20):
                            if chunk_clean[i:i+40] in ev_clean:
                                is_used = True
                                break
                    if is_used:
                        used_chunks.append(c)
            
            # Fallback to the top candidate if sliding window misses (e.g. LLM rephrased)
            if not used_chunks and all_expanded and merged_evidence != "NO_EVIDENCE":
                used_chunks = [all_expanded[0]]
                
            sources = _format_sources(used_chunks)

            is_confident = check_confidence(all_expanded, question)
            if not is_confident:
                db.add_all([
                    Message(session_id=session_id, role="user", content=question),
                    Message(session_id=session_id, role="assistant", content=NOT_AVAILABLE, sources=[]),
                ])
                await db.commit()
                yield f"data: {json.dumps({'type': 'token', 'content': NOT_AVAILABLE})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'sources': [], 'session_id': session_id})}\n\n"
                return

            # ── Stream the answer ────────────────────────────────────────────
            full_answer = ""
            async with request.app.state.llm_semaphore:
                async for token in stream_answer_from_evidence(question, merged_evidence, all_expanded, history):
                    full_answer += token
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            # Normalise N/A indicators that the model may emit in text
            na_indicators = [
                "information is not available", "not mentioned in the provided",
                "not specified in the provided", "does not mention", "does not specify",
                "does not provide", "not clear from", "cannot be determined",
                "the regulations do not explicitly state this",
            ]
            if any(ind in full_answer.lower() for ind in na_indicators):
                full_answer = NOT_AVAILABLE
                sources = []

            db.add_all([
                Message(session_id=session_id, role="user", content=question),
                Message(session_id=session_id, role="assistant", content=full_answer,
                        sources=[s if isinstance(s, dict) else s.__dict__ for s in sources]),
            ])
            await db.commit()

            import os
            from backend.config import PROJECT_ROOT
            raw_dir = PROJECT_ROOT / "data" / "raw"
            title_to_file = {}
            if raw_dir.is_dir():
                for f in os.listdir(raw_dir):
                    if f.endswith(".pdf"):
                        t = f.replace(".pdf", "").replace("_", " ").title()
                        title_to_file[t] = f

            sources_payload = []
            for s in sources:
                s_dict = s if isinstance(s, dict) else {"document": s.document, "page": s.page}
                s_dict["filename"] = title_to_file.get(s_dict["document"])
                sources_payload.append(s_dict)

            yield f"data: {json.dumps({'type': 'done', 'sources': sources_payload, 'session_id': session_id})}\n\n"

        except Exception:
            logger.exception("Error in streaming pipeline")
            yield f"data: {json.dumps({'type': 'error', 'content': 'An internal error occurred.'})}\n\n"

    return StreamingResponse(
        _pipeline_then_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering if behind a proxy
        },
    )

